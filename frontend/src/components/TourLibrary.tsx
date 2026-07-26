import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  CircleAlert,
  Footprints,
  LogOut,
  Plus,
  Sparkles
} from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import { loadCreditBalance, loadTours, supabase } from "../lib/supabase";
import { ACTIVE_STATUSES, type Tour } from "../types";
import { CreateTourDialog } from "./CreateTourDialog";
import { TourDetail } from "./TourDetail";
import { TourList } from "./TourList";

export function TourLibrary({ session }: { session: Session }) {
  const online = useOnlineStatus();
  const [tours, setTours] = useState<Tour[]>([]);
  const [credits, setCredits] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    new URLSearchParams(window.location.hash.slice(1)).get("tour")
  );
  const [libraryLoaded, setLibraryLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const refreshTours = useCallback(async () => {
    try {
      setTours(await loadTours());
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load tours");
    }
  }, []);

  const refreshLibrary = useCallback(async () => {
    try {
      const [nextTours, nextCredits] = await Promise.all([
        loadTours(),
        loadCreditBalance()
      ]);
      setTours(nextTours);
      setCredits(nextCredits);
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load tours");
    }
  }, []);

  useEffect(() => {
    if (!online) {
      setLibraryLoaded(true);
      return;
    }
    setLibraryLoaded(false);
    void refreshLibrary().finally(() => setLibraryLoaded(true));
  }, [online, refreshLibrary]);

  useEffect(() => {
    if (!online || !tours.some((tour) => ACTIVE_STATUSES.includes(tour.status))) {
      return;
    }
    const timer = window.setInterval(() => void refreshTours(), 3000);
    return () => window.clearInterval(timer);
  }, [online, refreshTours, tours]);

  useEffect(() => {
    if (!online) return;
    const handleFocus = () => void refreshTours();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [online, refreshTours]);

  const visibleTours = online ? tours : [];

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
          <div><p className="eyebrow">Your library</p><h2>Walking tours</h2></div>
          <span className="credit-pill">{credits ?? "—"} credits</span>
        </div>
        <button
          className="primary-button wide"
          onClick={() => setShowCreate(true)}
          disabled={!online}
        >
          <Plus size={18} /> New tour
        </button>
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
          />
        </div>
        <footer className="sidebar-footer">
          <span className={`connection-dot ${online ? "online" : ""}`} />
          {online ? session.user.email : "Offline mode"}
        </footer>
      </aside>

      <section className={`content ${selectedId ? "has-selection" : ""}`}>
        {selectedId ? (
          <TourDetail
            key={selectedId}
            tourId={selectedId}
            onBack={() => selectTour(null)}
            onChanged={refreshTours}
          />
        ) : (
          <WelcomePanel onCreate={() => setShowCreate(true)} />
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

function WelcomePanel({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="welcome-panel">
      <span className="welcome-icon"><Footprints size={34} /></span>
      <h1>Select a tour</h1>
      <p>Choose one from your library or create a new tour.</p>
      <button className="primary-button" onClick={onCreate}>
        <Sparkles size={18} />New tour
      </button>
    </div>
  );
}
