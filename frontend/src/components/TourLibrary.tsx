import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  BookOpen,
  CircleAlert,
  Compass,
  Footprints,
  LogOut,
  Plus,
  Sparkles
} from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import {
  loadCreditBalance,
  loadOwnedTours,
  loadPublicTours,
  supabase
} from "../lib/supabase";
import { ACTIVE_STATUSES, type Tour } from "../types";
import { CreateTourDialog } from "./CreateTourDialog";
import { TourDetail } from "./TourDetail";
import { TourList } from "./TourList";

export function TourLibrary({ session }: { session: Session }) {
  const online = useOnlineStatus();
  const [ownedTours, setOwnedTours] = useState<Tour[]>([]);
  const [publicTours, setPublicTours] = useState<Tour[]>([]);
  const [view, setView] = useState<"library" | "public">("library");
  const [credits, setCredits] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    new URLSearchParams(window.location.hash.slice(1)).get("tour")
  );
  const [libraryLoaded, setLibraryLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

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
      const [nextOwnedTours, nextPublicTours, nextCredits] = await Promise.all([
        loadOwnedTours(session.user.id),
        loadPublicTours(),
        loadCreditBalance()
      ]);
      setOwnedTours(nextOwnedTours);
      setPublicTours(nextPublicTours);
      setCredits(nextCredits);
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
    ? view === "library" ? ownedTours : publicTours
    : [];

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
      <aside className={`sidebar ${selectedId ? "has-selection" : ""}`}>
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
            <p className="eyebrow">{view === "library" ? "Your library" : "Community"}</p>
            <h2>{view === "library" ? "Walking tours" : "Public tours"}</h2>
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
        <div className="tour-list">
          <TourList
            tours={visibleTours}
            loading={!libraryLoaded}
            online={online}
            selectedId={selectedId}
            onSelect={selectTour}
            publicMode={view === "public"}
          />
        </div>
        <footer className="sidebar-footer">
          <span className={`connection-dot ${online ? "online" : ""}`} />
          {online ? session.user.email : "Offline mode"}
        </footer>
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
        </nav>
      </aside>

      <section className={`content ${selectedId ? "has-selection" : ""}`}>
        {selectedId ? (
          <TourDetail
            key={selectedId}
            tourId={selectedId}
            viewerId={session.user.id}
            onBack={() => selectTour(null)}
            onChanged={refreshLibrary}
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
