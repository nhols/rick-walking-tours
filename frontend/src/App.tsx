import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  CircleAlert,
  Download,
  Footprints,
  ChevronUp,
  LoaderCircle,
  LogOut,
  MapPin,
  MessageCircle,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2
} from "lucide-react";
import { CheckpointMap } from "./components/CheckpointMap";
import { ChapterAudio } from "./components/ChapterAudio";
import { workerCommand, type CommandAccepted } from "./lib/api";
import {
  getDownloadedTours,
  removeDownloadedTour,
  saveChapterAudio,
  saveDownloadedTour
} from "./lib/offline";
import {
  loadCreditBalance,
  loadTourBundle,
  loadTours,
  supabase
} from "./lib/supabase";
import type {
  DownloadedTour,
  Tour,
  TourBundle,
  TourStatus
} from "./types";

const ACTIVE_STATUSES: TourStatus[] = [
  "researching",
  "writing_chapters",
  "generating_audio"
];

const STATUS_LABELS: Record<TourStatus, string> = {
  researching: "Researching checkpoints",
  awaiting_review: "Awaiting your review",
  writing_chapters: "Writing chapters",
  generating_audio: "Generating audio",
  ready: "Ready to walk",
  failed: "Needs attention"
};

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    void (async () => {
      const { data } = await supabase.auth.getSession();
      const sessionIsValid = !data.session || !(await supabase.auth.getUser()).error;
      if (!sessionIsValid) {
        await supabase.auth.signOut({ scope: "local" });
      }
      if (active) setSession(sessionIsValid ? data.session : null);
    })();
    const { data } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (event === "INITIAL_SESSION") return;
      setSession(nextSession);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  if (session === undefined) {
    return <FullPageLoader />;
  }
  if (!session) {
    return <AuthScreen />;
  }
  return <TourApp session={session} />;
}

function AuthScreen() {
  const [email, setEmail] = useState("demo@rick.local");
  const [password, setPassword] = useState("password123");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const result =
      mode === "login"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (result.error) {
      setMessage(result.error.message);
    } else if (mode === "signup" && !result.data.session) {
      setMessage("Check your email to confirm your account, then sign in.");
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <div className="brand-lockup">
          <span className="brand-mark"><Footprints size={24} /></span>
          <span>Rick</span>
        </div>
        <p className="eyebrow">Stories for the street</p>
        <h1>A local guide,<br />made for your walk.</h1>
        <p className="auth-copy">
          Shape a route with the tour maker, then carry every story and chapter
          with you—even when your signal disappears.
        </p>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <p className="eyebrow">{mode === "login" ? "Welcome back" : "Create account"}</p>
          <h2>{mode === "login" ? "Sign in to your tours" : "Start exploring"}</h2>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={6}
              required
            />
          </label>
          {message && <p className="form-message">{message}</p>}
          <button className="primary-button wide" disabled={busy}>
            {busy && <LoaderCircle className="spin" size={18} />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setMessage(null);
            }}
          >
            {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

function TourApp({ session }: { session: Session }) {
  const [tours, setTours] = useState<Tour[]>([]);
  const [downloaded, setDownloaded] = useState<DownloadedTour[]>([]);
  const [credits, setCredits] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    new URLSearchParams(window.location.hash.slice(1)).get("tour")
  );
  const [bundle, setBundle] = useState<TourBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    const localTours = await getDownloadedTours();
    setDownloaded(localTours);
    try {
      if (!navigator.onLine) throw new Error("offline");
      const [nextTours, nextCredits] = await Promise.all([
        loadTours(),
        loadCreditBalance()
      ]);
      setTours(nextTours);
      setCredits(nextCredits);
      setError(null);
      if (selectedId) setBundle(await loadTourBundle(selectedId));
    } catch (refreshError) {
      if (selectedId) {
        const local = localTours.find((item) => item.tourId === selectedId);
        if (local) setBundle(local.bundle);
      }
      if (navigator.onLine) {
        setError(refreshError instanceof Error ? refreshError.message : "Could not load tours");
      }
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const needsPolling = tours.some((tour) => ACTIVE_STATUSES.includes(tour.status));
    if (!needsPolling) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [refresh, tours]);

  useEffect(() => {
    const handleOnline = () => void refresh();
    const selectedTour = tours.find((tour) => tour.id === selectedId);
    const shouldRefreshOnFocus =
      !selectedId || !selectedTour || ACTIVE_STATUSES.includes(selectedTour.status);
    const handleFocus = () => {
      if (shouldRefreshOnFocus) void refresh();
    };
    window.addEventListener("online", handleOnline);
    window.addEventListener("focus", handleFocus);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("focus", handleFocus);
    };
  }, [refresh, selectedId, tours]);

  const visibleTours = useMemo(() => {
    const merged = [...tours];
    for (const item of downloaded) {
      if (!merged.some((tour) => tour.id === item.tourId)) merged.push(item.bundle.tour);
    }
    return merged.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }, [downloaded, tours]);

  function selectTour(tourId: string | null) {
    setSelectedId(tourId);
    setBundle(null);
    const hash = tourId ? `tour=${encodeURIComponent(tourId)}` : "";
    window.history.replaceState(null, "", `${window.location.pathname}${hash ? `#${hash}` : ""}`);
  }

  async function downloadTour(tourId: string) {
    if (downloadingIds.has(tourId) || downloaded.some((item) => item.tourId === tourId)) {
      return;
    }
    setDownloadingIds((current) => new Set(current).add(tourId));
    try {
      const nextBundle = await loadTourBundle(tourId);
      const availableChapters = nextBundle.chapters.filter((chapter) => chapter.audio_path);
      for (const chapter of availableChapters) {
        const { data, error: downloadError } = await supabase.storage
          .from("tour-audio")
          .download(chapter.audio_path!);
        if (downloadError) throw downloadError;
        await saveChapterAudio(chapter.id, data);
      }
      await saveDownloadedTour(nextBundle);
      setDownloaded(await getDownloadedTours());
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Download failed");
    } finally {
      setDownloadingIds((current) => {
        const next = new Set(current);
        next.delete(tourId);
        return next;
      });
    }
  }

  async function deleteDownload(tourId: string) {
    try {
      await removeDownloadedTour(tourId);
      setDownloaded(await getDownloadedTours());
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Could not remove download");
    }
  }

  const downloadedIds = new Set(downloaded.map((item) => item.tourId));

  return (
    <main className="app-shell">
      <aside className={`sidebar ${selectedId ? "has-selection" : ""}`}>
        <header className="sidebar-header">
          <div className="brand-lockup compact">
            <span className="brand-mark"><Footprints size={20} /></span>
            <span>Rick</span>
          </div>
          <button className="icon-button" title="Sign out" onClick={() => void supabase.auth.signOut()}>
            <LogOut size={19} />
          </button>
        </header>
        <div className="library-heading">
          <div>
            <p className="eyebrow">Your library</p>
            <h2>Walking tours</h2>
          </div>
          <span className="credit-pill">{credits ?? "—"} credits</span>
        </div>
        <button className="primary-button wide" onClick={() => setShowCreate(true)} disabled={!navigator.onLine}>
          <Plus size={18} /> New tour
        </button>
        {error && <div className="error-banner"><CircleAlert size={17} />{error}</div>}
        <div className="tour-list">
          {loading && visibleTours.length === 0 ? (
            <div className="list-loader"><LoaderCircle className="spin" />Loading tours…</div>
          ) : visibleTours.length === 0 ? (
            <div className="empty-list"><MapPin size={24} /><p>No tours yet.</p><small>Create one to begin.</small></div>
          ) : (
            <>
              <TourSection
                title="In progress"
                tours={visibleTours.filter((tour) => tour.status !== "ready")}
                selectedId={selectedId}
                downloadedIds={downloadedIds}
                downloadingIds={downloadingIds}
                onSelect={selectTour}
                onDownload={(tourId) => void downloadTour(tourId)}
                onRemoveDownload={(tourId) => void deleteDownload(tourId)}
              />
              <TourSection
                title="Ready to walk"
                tours={visibleTours.filter((tour) => tour.status === "ready")}
                selectedId={selectedId}
                downloadedIds={downloadedIds}
                downloadingIds={downloadingIds}
                onSelect={selectTour}
                onDownload={(tourId) => void downloadTour(tourId)}
                onRemoveDownload={(tourId) => void deleteDownload(tourId)}
              />
            </>
          )}
        </div>
        <footer className="sidebar-footer">
          <span className={`connection-dot ${navigator.onLine ? "online" : ""}`} />
          {navigator.onLine ? session.user.email : "Offline mode"}
        </footer>
      </aside>

      <section className={`content ${selectedId ? "has-selection" : ""}`}>
        {selectedId ? (
          bundle ? (
            <TourDetail
              bundle={bundle}
              onBack={() => selectTour(null)}
              onChanged={refresh}
            />
          ) : (
            <FullPageLoader />
          )
        ) : (
          <WelcomePanel onCreate={() => setShowCreate(true)} />
        )}
      </section>

      {showCreate && (
        <CreateTourDialog
          onClose={() => setShowCreate(false)}
          onCreated={async (tourId) => {
            setShowCreate(false);
            await refresh();
            selectTour(tourId);
          }}
        />
      )}
    </main>
  );
}

function TourSection({
  title,
  tours,
  selectedId,
  downloadedIds,
  downloadingIds,
  onSelect,
  onDownload,
  onRemoveDownload
}: {
  title: string;
  tours: Tour[];
  selectedId: string | null;
  downloadedIds: Set<string>;
  downloadingIds: Set<string>;
  onSelect: (id: string) => void;
  onDownload: (id: string) => void;
  onRemoveDownload: (id: string) => void;
}) {
  if (tours.length === 0) return null;
  return (
    <section className="tour-section">
      <p className="section-label">{title}</p>
      {tours.map((tour) => {
        const isDownloaded = downloadedIds.has(tour.id);
        const isDownloading = downloadingIds.has(tour.id);
        const tourName = tour.title ?? tour.input.location;
        return (
          <div
            className={`tour-row ${selectedId === tour.id ? "selected" : ""}`}
            key={tour.id}
          >
            <button className="tour-row-main" onClick={() => onSelect(tour.id)}>
              <span className="tour-row-icon"><MapPin size={18} /></span>
              <span className="tour-row-copy">
                <strong>{tourName}</strong>
                <small>{STATUS_LABELS[tour.status]}</small>
              </span>
              <ChevronRight size={17} />
            </button>
            {tour.status === "ready" && (
              <button
                className={`tour-download-button ${isDownloaded ? "is-downloaded" : ""}`}
                type="button"
                aria-label={
                  isDownloaded
                    ? `${tourName} downloaded`
                    : isDownloading
                      ? `Downloading ${tourName}`
                      : `Download ${tourName} for offline listening`
                }
                title={isDownloaded ? "Remove offline download" : isDownloading ? "Downloading…" : "Download for offline listening"}
                disabled={isDownloading}
                onClick={() => isDownloaded ? onRemoveDownload(tour.id) : onDownload(tour.id)}
              >
                {isDownloading ? (
                  <LoaderCircle className="spin" size={18} />
                ) : isDownloaded ? (
                  <span className="downloaded-state-icons">
                    <Check className="downloaded-check" size={18} />
                    <Trash2 className="remove-download" size={17} />
                  </span>
                ) : (
                  <Download size={18} />
                )}
              </button>
            )}
          </div>
        );
      })}
    </section>
  );
}

function WelcomePanel({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="welcome-panel">
      <span className="welcome-icon"><Footprints size={34} /></span>
      <p className="eyebrow">Choose your own path</p>
      <h1>Where should we walk next?</h1>
      <p>Select a tour from your library, or work with Rick to create a new route.</p>
      <button className="primary-button" onClick={onCreate}><Sparkles size={18} />Create a tour</button>
    </div>
  );
}

function CreateTourDialog({
  onClose,
  onCreated
}: {
  onClose: () => void;
  onCreated: (tourId: string) => void;
}) {
  const [location, setLocation] = useState("");
  const [request, setRequest] = useState("");
  const [minStops, setMinStops] = useState(2);
  const [maxStops, setMaxStops] = useState(10);
  const [maxDistanceKm, setMaxDistanceKm] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const command = await workerCommand<CommandAccepted>("create", {
        location,
        request,
        min_stops: minStops,
        max_stops: maxStops,
        max_checkpoint_distance_km: maxDistanceKm
      });
      onCreated(command.tour_id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not create tour");
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <form className="dialog" onSubmit={submit}>
        <p className="eyebrow">New walking tour</p>
        <h2>Tell Rick what you want to explore</h2>
        <label>
          Place
          <input placeholder="e.g. Edinburgh Old Town" value={location} onChange={(event) => setLocation(event.target.value)} required />
        </label>
        <label>
          What are you interested in?
          <textarea placeholder="A literary walk with hidden stories, around 45 minutes…" value={request} onChange={(event) => setRequest(event.target.value)} required rows={5} />
        </label>
        <div className="form-grid">
          <label>
            Minimum stops
            <input
              type="number"
              min={1}
              max={20}
              value={minStops}
              onChange={(event) => setMinStops(event.currentTarget.valueAsNumber)}
              required
            />
          </label>
          <label>
            Maximum stops
            <input
              type="number"
              min={minStops}
              max={20}
              value={maxStops}
              onChange={(event) => setMaxStops(event.currentTarget.valueAsNumber)}
              required
            />
          </label>
        </div>
        <label>
          Maximum distance between any two stops (km)
          <input
            type="number"
            min={0.1}
            max={100}
            step="any"
            value={maxDistanceKm}
            onChange={(event) => setMaxDistanceKm(event.currentTarget.valueAsNumber)}
            required
          />
        </label>
        {error && <p className="form-message">{error}</p>}
        {busy && <p className="working-note"><LoaderCircle className="spin" size={17} />Researching and planning your first route…</p>}
        <div className="dialog-actions">
          <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="primary-button" disabled={busy}><Sparkles size={17} />Start planning</button>
        </div>
      </form>
    </div>
  );
}

function TourDetail({
  bundle,
  onBack,
  onChanged
}: {
  bundle: TourBundle;
  onBack: () => void;
  onChanged: () => Promise<void>;
}) {
  const isReady = bundle.tour.status === "ready";
  return (
    <div className={`detail-page ${isReady ? "is-ready" : ""}`}>
      <header className="detail-header">
        <button className="back-button" aria-label="Back to library" title="Back to library" onClick={onBack}>
          <ArrowLeft size={21} />
        </button>
        <div className="detail-title">
          <p className="eyebrow">{bundle.tour.input.location}</p>
          <h1>{bundle.tour.title ?? "Tour in progress"}</h1>
        </div>
      </header>
      {isReady ? (
        <ReadyTour bundle={bundle} />
      ) : (
        <GenerationReview bundle={bundle} onChanged={onChanged} />
      )}
    </div>
  );
}

function ReadyTour({ bundle }: { bundle: TourBundle }) {
  const approvedPlan = bundle.plans.find((plan) => plan.id === bundle.tour.approved_plan_id) ?? bundle.plans.at(-1);
  const checkpoints = approvedPlan?.checkpoints ?? [];
  const [selectedId, setSelectedId] = useState(checkpoints[0]?.id);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const selected = checkpoints.find((item) => item.id === selectedId) ?? checkpoints[0];
  const chapter = bundle.chapters.find((item) => item.checkpoint_id === selected?.id);

  return (
    <div className="ready-tour">
      <div className="ready-map">
        <CheckpointMap checkpoints={checkpoints} selectedId={selected?.id} onSelect={setSelectedId} />
      </div>
      {selected && (
        <div className={`player-shell ${detailsOpen ? "is-expanded" : ""}`}>
          <aside
            className="checkpoint-details-overlay"
            aria-label="Checkpoint details"
            aria-hidden={!detailsOpen}
          >
            <article className="chapter-card">
              <div className="chapter-number">Stop {selected.position}</div>
              <h2>{chapter?.title ?? selected.title}</h2>
              <a
                className="address"
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${selected.lat},${selected.lon}`)}`}
                target="_blank"
                rel="noreferrer"
                tabIndex={detailsOpen ? 0 : -1}
              >
                <MapPin size={16} />
                {selected.formatted_address ?? "Open in Maps"}
              </a>
              <p className="transcript">{chapter?.narration ?? selected.description}</p>
            </article>
          </aside>
          <section className="player-dock">
            <button
              className="player-details-trigger"
              type="button"
              onClick={() => setDetailsOpen((open) => !open)}
              aria-expanded={detailsOpen}
              aria-label={`${detailsOpen ? "Collapse" : "Open"} details for ${chapter?.title ?? selected.title}`}
            >
              <span>
                <small>Stop {selected.position} of {checkpoints.length}</small>
                <strong>{chapter?.title ?? selected.title}</strong>
              </span>
              <ChevronUp className={`details-chevron ${detailsOpen ? "is-open" : ""}`} size={21} />
            </button>
            <div className="player-audio">
              {chapter ? <ChapterAudio chapter={chapter} /> : <span>Audio unavailable</span>}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function GenerationReview({
  bundle,
  onChanged
}: {
  bundle: TourBundle;
  onChanged: () => Promise<void>;
}) {
  const currentPlan = bundle.plans.at(-1);
  const [selectedPlanId, setSelectedPlanId] = useState(currentPlan?.id);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string>();
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState<"approve" | "feedback" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedPlan = bundle.plans.find((plan) => plan.id === selectedPlanId) ?? currentPlan;
  const canReview = bundle.tour.status === "awaiting_review" && currentPlan;
  const latestError = bundle.statusEvents.at(-1)?.details?.error;

  useEffect(() => {
    setSelectedPlanId(currentPlan?.id);
    setSelectedCheckpointId(currentPlan?.checkpoints[0]?.id);
  }, [currentPlan?.id]);

  async function approve() {
    if (!currentPlan) return;
    setBusy("approve");
    setError(null);
    try {
      await workerCommand("approve", {
        tour_id: bundle.tour.id,
        plan_id: currentPlan.id
      });
      await onChanged();
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Approval failed");
    } finally {
      setBusy(null);
    }
  }

  async function submitFeedback(event: FormEvent) {
    event.preventDefault();
    if (!currentPlan || !feedback.trim()) return;
    setBusy("feedback");
    setError(null);
    try {
      await workerCommand("feedback", {
        tour_id: bundle.tour.id,
        plan_id: currentPlan.id,
        feedback: feedback.trim()
      });
      setFeedback("");
      await onChanged();
    } catch (feedbackError) {
      setError(feedbackError instanceof Error ? feedbackError.message : "Feedback failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="review-layout">
      <section className="revision-column">
        <div className={`progress-card ${bundle.tour.status === "failed" ? "failed" : ""}`}>
          {ACTIVE_STATUSES.includes(bundle.tour.status) ? <LoaderCircle className="spin" size={21} /> : bundle.tour.status === "failed" ? <CircleAlert size={21} /> : <MessageCircle size={21} />}
          <div>
            <strong>{STATUS_LABELS[bundle.tour.status]}</strong>
            <span>{latestError ?? "Your plan is ready."}</span>
          </div>
        </div>
        <div className="conversation">
          <div className="message user-message"><small>You</small><p>{bundle.tour.input.request}</p></div>
          {bundle.plans.map((plan) => (
            <div className="revision-thread" key={plan.id}>
              {plan.feedback && <div className="message user-message"><small>You · feedback</small><p>{plan.feedback}</p></div>}
              <button className={`message agent-message ${selectedPlan?.id === plan.id ? "selected" : ""}`} onClick={() => { setSelectedPlanId(plan.id); setSelectedCheckpointId(plan.checkpoints[0]?.id); }}>
                <small>Rick · revision {plan.revision}</small>
                <strong>{plan.narrative_arc}</strong>
                <span>{plan.checkpoints.length} checkpoints · View plan</span>
              </button>
            </div>
          ))}
          {ACTIVE_STATUSES.includes(bundle.tour.status) && <div className="message agent-thinking"><LoaderCircle className="spin" size={16} />Rick is working…</div>}
        </div>
        {canReview && (
          <form className="feedback-form" onSubmit={submitFeedback}>
            <label htmlFor="feedback">What should change?</label>
            <div className="feedback-input">
              <textarea id="feedback" rows={3} placeholder="Add a stop about industrial history…" value={feedback} onChange={(event) => setFeedback(event.target.value)} disabled={Boolean(busy)} />
              <button className="send-button" disabled={!feedback.trim() || Boolean(busy)} title="Send feedback">
                {busy === "feedback" ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
              </button>
            </div>
            <button className="approve-button" type="button" onClick={() => void approve()} disabled={Boolean(busy)}>
              {busy === "approve" ? <LoaderCircle className="spin" size={18} /> : <Check size={18} />}
              Approve this plan and create tour
            </button>
          </form>
        )}
        {error && <p className="form-message padded">{error}</p>}
      </section>
      <section className="plan-column">
        {selectedPlan ? (
          <>
            <div className="plan-map"><CheckpointMap checkpoints={selectedPlan.checkpoints} selectedId={selectedCheckpointId} onSelect={setSelectedCheckpointId} /></div>
            <div className="plan-summary">
              <p className="section-label">Revision {selectedPlan.revision} · chapter briefs</p>
              <h2>{selectedPlan.narrative_arc}</h2>
              <div className="brief-list">
                {selectedPlan.checkpoints.map((checkpoint) => (
                  <button className={selectedCheckpointId === checkpoint.id ? "active" : ""} key={checkpoint.id} onClick={() => setSelectedCheckpointId(checkpoint.id)}>
                    <span className="number-dot">{checkpoint.position}</span>
                    <span><strong>{checkpoint.title}</strong><small>{checkpoint.description}</small></span>
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="plan-empty"><RefreshCw className="spin-slow" /><h2>Building your first route</h2><p>Checkpoints will appear here as soon as the plan is ready.</p></div>
        )}
      </section>
    </div>
  );
}

function FullPageLoader() {
  return <div className="full-loader"><LoaderCircle className="spin" size={26} />Loading Rick…</div>;
}
