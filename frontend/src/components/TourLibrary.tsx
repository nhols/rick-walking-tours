import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  BookOpen,
  CircleAlert,
  Compass,
  Footprints,
  LogOut,
  Plus,
  Sparkles,
  UserRound
} from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import { loadCreditBalance } from "../lib/credits";
import { loadProfileStats } from "../lib/profile";
import { supabase } from "../lib/supabase";
import { loadOwnedTours, loadPublicTours } from "../lib/tours";
import { ACTIVE_STATUSES, type ProfileStats, type Tour } from "../types";
import { CompletionDialog } from "./CompletionDialog";
import { CreateTourDialog } from "./CreateTourDialog";
import { ProfilePanel } from "./ProfilePanel";
import { TourDetail } from "./TourDetail";
import { TourList } from "./TourList";

export function TourLibrary({ session }: { session: Session }) {
  const online = useOnlineStatus();
  const [ownedTours, setOwnedTours] = useState<Tour[]>([]);
  const [publicTours, setPublicTours] = useState<Tour[]>([]);
  const [view, setView] = useState<"library" | "public" | "profile">("library");
  const [credits, setCredits] = useState<number | null>(null);
  const [profileStats, setProfileStats] = useState<ProfileStats | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    new URLSearchParams(window.location.hash.slice(1)).get("tour")
  );
  const [libraryLoaded, setLibraryLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [completionTour, setCompletionTour] = useState<Tour | null>(null);

  const refreshTours = useCallback(async () => {
    try {
      setOwnedTours(await loadOwnedTours(session.user.id));
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load tours");
    }
  }, [session.user.id]);

  const refreshLibrary = useCallback(async () => {
    try {
      const [nextOwnedTours, nextPublicTours, nextCredits, nextProfileStats] = await Promise.all([
        loadOwnedTours(session.user.id),
        loadPublicTours(),
        loadCreditBalance(),
        loadProfileStats()
      ]);
      setOwnedTours(nextOwnedTours);
      setPublicTours(nextPublicTours);
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
    const timer = window.setInterval(() => void refreshTours(), 3000);
    return () => window.clearInterval(timer);
  }, [online, ownedTours, refreshTours]);

  useEffect(() => {
    if (!online) return;
    const handleFocus = () => void refreshLibrary();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [online, refreshLibrary]);

  const visibleTours = online
    ? view === "library" ? ownedTours : view === "public" ? publicTours : []
    : [];

  const viewCopy = view === "library"
    ? { eyebrow: "Your library", heading: "Walking tours" }
    : view === "public"
      ? { eyebrow: "Community", heading: "Public tours" }
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

  return (
    <main className="app-shell">
      <aside className={`sidebar ${selectedId ? "has-selection" : ""} ${view === "profile" ? "profile-active" : ""}`}>
        <header className="sidebar-header">
          <div className="brand-lockup compact">
            <span className="brand-mark"><Footprints size={20} /></span>
            <span>Rick</span>
          </div>
          <button
            className="icon-button"
            title="Sign out"
            onClick={() => void supabase.auth.signOut()}
          >
            <LogOut size={19} />
          </button>
        </header>
        <div className="library-heading">
          <div>
            <p className="eyebrow">{viewCopy.eyebrow}</p>
            <h2>{viewCopy.heading}</h2>
          </div>
          <span className="credit-pill">{credits ?? "—"} credits</span>
        </div>
        {view === "library" && (
          <button
            className="primary-button wide"
            onClick={() => setShowCreate(true)}
            disabled={!online}
          >
            <Plus size={18} /> New tour
          </button>
        )}
        {loadError && (
          <div className="error-banner">
            <CircleAlert size={17} />{loadError}
          </div>
        )}
        {view !== "profile" ? (
          <div className="tour-list">
            <TourList
              tours={visibleTours}
              loading={!libraryLoaded}
              online={online}
              selectedId={selectedId}
              onSelect={selectTour}
              onComplete={setCompletionTour}
              publicMode={view === "public"}
            />
          </div>
        ) : (
          <p className="profile-sidebar-copy">
            Account details and lifetime activity across Rick.
          </p>
        )}
        <nav className="home-nav" aria-label="Tour collections">
          <button
            className={view === "library" ? "active" : ""}
            aria-label="Your library"
            title="Your library"
            onClick={() => setView("library")}
          >
            <BookOpen size={21} />
          </button>
          <button
            className={view === "public" ? "active" : ""}
            aria-label="Browse public tours"
            title="Browse public tours"
            onClick={() => setView("public")}
          >
            <Compass size={22} />
          </button>
          <button
            className={view === "profile" ? "active" : ""}
            aria-label="Profile and stats"
            title="Profile and stats"
            onClick={() => {
              selectTour(null);
              setView("profile");
            }}
          >
            <UserRound size={21} />
          </button>
        </nav>
        <footer className="sidebar-footer">
          <span className={`connection-dot ${online ? "online" : ""}`} />
          {online ? session.user.email : "Offline mode"}
        </footer>
      </aside>

      <section className={`content ${selectedId ? "has-selection" : ""} ${view === "profile" ? "show-profile" : ""}`}>
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
        ) : (
          <WelcomePanel
            publicMode={view === "public"}
            onCreate={() => setShowCreate(true)}
          />
        )}
      </section>

      {showCreate && (
        <CreateTourDialog
          onClose={() => setShowCreate(false)}
          onCreated={(tourId) => {
            setShowCreate(false);
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
  publicMode,
  onCreate
}: {
  publicMode: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="welcome-panel">
      <span className="welcome-icon">
        {publicMode ? <Compass size={34} /> : <Footprints size={34} />}
      </span>
      <h1>{publicMode ? "Explore public tours" : "Select a tour"}</h1>
      <p>
        {publicMode
          ? "Choose a walk shared by another Rick user."
          : "Choose one from your library or create a new tour."}
      </p>
      {!publicMode && (
        <button className="primary-button" onClick={onCreate}>
          <Sparkles size={18} />New tour
        </button>
      )}
    </div>
  );
}
