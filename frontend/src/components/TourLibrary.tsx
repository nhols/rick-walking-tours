import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  BookOpen,
  Check,
  CircleAlert,
  Footprints,
  Hammer,
  List,
  LogOut,
  Map as MapIcon,
  Plus,
  Sparkles,
  UserRound,
  X
} from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import { loadCreditBalance } from "../lib/credits";
import { loadProfileStats } from "../lib/profile";
import { supabase } from "../lib/supabase";
import { loadLibraryTours, loadOwnedTours } from "../lib/tours";
import { ACTIVE_STATUSES, type ProfileStats, type Tour } from "../types";
import { CompletionDialog } from "./CompletionDialog";
import { CreateTourDialog } from "./CreateTourDialog";
import { LibraryMap } from "./LibraryMap";
import { ProfilePanel } from "./ProfilePanel";
import { TourDetail } from "./TourDetail";
import { TourList } from "./TourList";

type View = "build" | "library" | "profile";
type LibraryFilter = "all" | "yours" | "community";
type LibraryMode = "list" | "map";

export function TourLibrary({ session }: { session: Session }) {
  const online = useOnlineStatus();
  const [ownedTours, setOwnedTours] = useState<Tour[]>([]);
  const [libraryTours, setLibraryTours] = useState<Tour[]>([]);
  const [view, setView] = useState<View>("library");
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>("all");
  const [completedOnly, setCompletedOnly] = useState(false);
  const [libraryMode, setLibraryMode] = useState<LibraryMode>("list");
  const [clusterTours, setClusterTours] = useState<Tour[] | null>(null);
  const [credits, setCredits] = useState<number | null>(null);
  const [profileStats, setProfileStats] = useState<ProfileStats | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    new URLSearchParams(window.location.hash.slice(1)).get("tour")
  );
  const [libraryLoaded, setLibraryLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [completionTour, setCompletionTour] = useState<Tour | null>(null);

  const refreshLibrary = useCallback(async () => {
    try {
      const [nextOwnedTours, nextLibraryTours, nextCredits, nextProfileStats] =
        await Promise.all([
          loadOwnedTours(session.user.id),
          loadLibraryTours(session.user.id),
          loadCreditBalance(),
          loadProfileStats()
        ]);
      setOwnedTours(nextOwnedTours);
      setLibraryTours(nextLibraryTours);
      setCredits(nextCredits);
      setProfileStats(nextProfileStats);
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load tours");
    }
  }, [session.user.id]);

  useEffect(() => {
    if (!online) {
      setLibraryLoaded(true);
      return;
    }
    setLibraryLoaded(false);
    void refreshLibrary().finally(() => setLibraryLoaded(true));
  }, [online, refreshLibrary]);

  useEffect(() => {
    if (!online || !ownedTours.some((tour) => ACTIVE_STATUSES.includes(tour.status))) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadOwnedTours(session.user.id)
        .then((nextOwnedTours) => {
          const becameReady = ownedTours.some(
            (previous) =>
              previous.status !== "ready" &&
              nextOwnedTours.some(
                (next) => next.id === previous.id && next.status === "ready"
              )
          );
          setOwnedTours(nextOwnedTours);
          if (becameReady) void refreshLibrary();
        })
        .catch((error) => {
          setLoadError(error instanceof Error ? error.message : "Could not load tours");
        });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [online, ownedTours, refreshLibrary, session.user.id]);

  useEffect(() => {
    if (!online) return;
    const handleFocus = () => void refreshLibrary();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [online, refreshLibrary]);

  const buildTours = online
    ? ownedTours.filter((tour) => tour.status !== "ready")
    : [];
  const filteredLibraryTours = online ? libraryTours.filter((tour) => {
    const ownerMatches =
      libraryFilter === "all" ||
      (libraryFilter === "yours" && tour.owner_id === session.user.id) ||
      (libraryFilter === "community" && tour.owner_id !== session.user.id);
    return ownerMatches && (!completedOnly || Boolean(tour.completed_at));
  }) : [];
  const sidebarTours =
    view === "build"
      ? buildTours
      : view === "library"
        ? clusterTours ?? filteredLibraryTours
        : [];

  const viewCopy =
    view === "build"
      ? { eyebrow: "Your tours", heading: "Build" }
      : view === "library"
        ? { eyebrow: "Walking tours", heading: "Library" }
        : { eyebrow: "Your account", heading: "Profile & stats" };

  function selectTour(tourId: string | null) {
    setSelectedId(tourId);
    const hash = tourId ? `tour=${encodeURIComponent(tourId)}` : "";
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${hash ? `#${hash}` : ""}`
    );
  }

  function changeView(nextView: View) {
    selectTour(null);
    setClusterTours(null);
    setView(nextView);
  }

  function changeLibraryFilter(nextFilter: LibraryFilter) {
    setLibraryFilter(nextFilter);
    setClusterTours(null);
  }

  return (
    <main className="app-shell">
      <aside
        className={`sidebar ${selectedId ? "has-selection" : ""} ${
          view === "profile" ? "profile-active" : ""
        } ${view === "library" && libraryMode === "map" ? "library-map-active" : ""}`}
      >
        <header className="sidebar-header">
          <div className="brand-lockup compact">
            <span className="brand-mark"><Footprints size={20} /></span>
            <span>Rick</span>
          </div>
          <div className="sidebar-account">
            <span className={`connection-dot ${online ? "online" : ""}`} />
            <span className="account-email" title={session.user.email}>
              {online ? session.user.email : "Offline"}
            </span>
            <button
              className="icon-button"
              title="Sign out"
              aria-label="Sign out"
              onClick={() => void supabase.auth.signOut()}
            >
              <LogOut size={19} />
            </button>
          </div>
        </header>

        <div className="library-heading">
          <div>
            <p className="eyebrow">{viewCopy.eyebrow}</p>
            <h2>{viewCopy.heading}</h2>
          </div>
          <span className="credit-pill">{credits ?? "—"} credits</span>
        </div>

        {view === "build" && (
          <button
            className="primary-button wide"
            onClick={() => setShowCreate(true)}
            disabled={!online}
          >
            <Plus size={18} /> New tour
          </button>
        )}

        {view === "library" && (
          <div className="library-controls">
            <div className="library-filter" aria-label="Filter library">
              {(["all", "yours", "community"] as const).map((filter) => (
                <button
                  type="button"
                  key={filter}
                  className={libraryFilter === filter ? "active" : ""}
                  onClick={() => changeLibraryFilter(filter)}
                >
                  {filter[0].toUpperCase() + filter.slice(1)}
                </button>
              ))}
            </div>
            <div className="library-control-row">
              <button
                type="button"
                className={`completed-filter ${completedOnly ? "active" : ""}`}
                aria-pressed={completedOnly}
                onClick={() => {
                  setCompletedOnly((completed) => !completed);
                  setClusterTours(null);
                }}
              >
                <Check size={14} /> Completed
              </button>
              <div className="library-view-toggle" aria-label="Library view">
                <button
                  type="button"
                  className={libraryMode === "list" ? "active" : ""}
                  aria-label="List view"
                  title="List view"
                  onClick={() => {
                    setLibraryMode("list");
                    setClusterTours(null);
                  }}
                >
                  <List size={16} />
                </button>
                <button
                  type="button"
                  className={libraryMode === "map" ? "active" : ""}
                  aria-label="Map view"
                  title="Map view"
                  onClick={() => setLibraryMode("map")}
                >
                  <MapIcon size={16} />
                </button>
              </div>
            </div>
          </div>
        )}

        {loadError && (
          <div className="error-banner">
            <CircleAlert size={17} />{loadError}
          </div>
        )}

        {view !== "profile" ? (
          <div className="tour-list">
            {clusterTours && (
              <div className="cluster-result-heading">
                <span>{clusterTours.length} tours here</span>
                <button
                  type="button"
                  onClick={() => setClusterTours(null)}
                  aria-label="Show all tours"
                  title="Show all tours"
                >
                  <X size={15} />
                </button>
              </div>
            )}
            <TourList
              tours={sidebarTours}
              loading={!libraryLoaded}
              online={online}
              selectedId={selectedId}
              viewerId={session.user.id}
              variant={view === "build" ? "build" : "library"}
              onSelect={selectTour}
              onComplete={setCompletionTour}
            />
          </div>
        ) : (
          <p className="profile-sidebar-copy">
            Account details and lifetime activity across Rick.
          </p>
        )}

        <nav className="home-nav" aria-label="Main navigation">
          <button
            className={view === "build" ? "active" : ""}
            aria-label="Build tours"
            title="Build"
            onClick={() => changeView("build")}
          >
            <Hammer size={21} />
          </button>
          <button
            className={view === "library" ? "active" : ""}
            aria-label="Tour library"
            title="Library"
            onClick={() => changeView("library")}
          >
            <BookOpen size={21} />
          </button>
          <button
            className={view === "profile" ? "active" : ""}
            aria-label="Profile and stats"
            title="Profile and stats"
            onClick={() => changeView("profile")}
          >
            <UserRound size={21} />
          </button>
        </nav>

      </aside>

      <section
        className={`content ${selectedId ? "has-selection" : ""} ${
          view === "profile" ? "show-profile" : ""
        } ${view === "library" && libraryMode === "map" ? "show-library-map" : ""}`}
      >
        {selectedId ? (
          <TourDetail
            key={selectedId}
            tourId={selectedId}
            viewerId={session.user.id}
            onBack={() => selectTour(null)}
            onChanged={refreshLibrary}
          />
        ) : view === "profile" ? (
          <ProfilePanel
            session={session}
            stats={profileStats}
            loading={!libraryLoaded}
          />
        ) : view === "library" && libraryMode === "map" ? (
          <LibraryMap
            tours={filteredLibraryTours}
            viewerId={session.user.id}
            clusterTours={clusterTours}
            onSelect={selectTour}
            onClusterChange={setClusterTours}
            onShowList={() => {
              setLibraryMode("list");
              setClusterTours(null);
            }}
          />
        ) : (
          <WelcomePanel
            buildMode={view === "build"}
            onCreate={() => setShowCreate(true)}
          />
        )}
      </section>

      {showCreate && (
        <CreateTourDialog
          onClose={() => setShowCreate(false)}
          onCreated={(tourId) => {
            setShowCreate(false);
            setView("build");
            selectTour(tourId);
            void refreshLibrary();
          }}
        />
      )}
      {completionTour && (
        <CompletionDialog
          tour={completionTour}
          viewerId={session.user.id}
          onClose={() => setCompletionTour(null)}
          onCompleted={refreshLibrary}
        />
      )}
    </main>
  );
}

function WelcomePanel({
  buildMode,
  onCreate
}: {
  buildMode: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="welcome-panel">
      <span className="welcome-icon">
        {buildMode ? <Hammer size={34} /> : <BookOpen size={34} />}
      </span>
      <h1>{buildMode ? "Build a walking tour" : "Choose a tour"}</h1>
      <p>
        {buildMode
          ? "Create a tour or continue one already underway."
          : "Choose a tour from your library, or explore the map."}
      </p>
      {buildMode && (
        <button className="primary-button" onClick={onCreate}>
          <Sparkles size={18} />New tour
        </button>
      )}
    </div>
  );
}
