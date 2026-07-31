import type { Session } from "@supabase/supabase-js";
import type { ReactNode } from "react";
import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  Footprints,
  Globe2,
  LoaderCircle,
  Mail,
  Map,
  MessageSquareText,
  Route,
  Star,
  UsersRound,
  WalletCards
} from "lucide-react";
import { formatDistance, formatDuration } from "../lib/routes";
import type { ProfileStats } from "../types";

interface MetricItem {
  icon: ReactNode;
  label: string;
  value: string;
}

export function ProfilePanel({
  session,
  stats,
  loading
}: {
  session: Session;
  stats: ProfileStats | null;
  loading: boolean;
}) {
  const joined = session.user.created_at
    ? new Intl.DateTimeFormat(undefined, {
        day: "numeric",
        month: "long",
        year: "numeric"
      }).format(new Date(session.user.created_at))
    : "—";

  return (
    <div className="profile-page">
      <header className="profile-hero">
        <span className="profile-avatar"><Footprints size={30} /></span>
        <div>
          <p className="eyebrow">Your Rick account</p>
          <h1>Profile &amp; stats</h1>
          <p>Your walking-tour story so far.</p>
        </div>
      </header>

      <ProfileSection
        title="Account"
        items={[
          { icon: <Mail size={18} />, label: "Email", value: session.user.email ?? "—" },
          { icon: <CalendarDays size={18} />, label: "Member since", value: joined },
          {
            icon: <WalletCards size={18} />,
            label: "Credits",
            value: stats ? String(stats.credits) : "—"
          }
        ]}
      />

      {loading && !stats ? (
        <div className="profile-loader"><LoaderCircle className="spin" />Loading stats…</div>
      ) : stats ? (
        <>
          <ProfileSection
            title="Tours created"
            items={[
              { icon: <Map size={18} />, label: "Ready tours", value: String(stats.created.ready_tours) },
              { icon: <Globe2 size={18} />, label: "Public tours", value: String(stats.created.public_tours) },
              { icon: <Route size={18} />, label: "Planned distance", value: formatDistance(stats.created.distance_meters) },
              { icon: <Clock3 size={18} />, label: "Estimated walking time", value: formatDuration(stats.created.duration_seconds) }
            ]}
          />
          <ProfileSection
            title="Tours completed"
            items={[
              { icon: <CheckCircle2 size={18} />, label: "Completed tours", value: String(stats.completed.tours) },
              { icon: <Route size={18} />, label: "Planned distance", value: formatDistance(stats.completed.distance_meters) },
              { icon: <Clock3 size={18} />, label: "Estimated walking time", value: formatDuration(stats.completed.duration_seconds) }
            ]}
          />
          <ProfileSection
            title="Community walks"
            subtitle="Other users completing your public tours"
            items={[
              { icon: <Footprints size={18} />, label: "Completions", value: String(stats.community.completions) },
              { icon: <UsersRound size={18} />, label: "Unique walkers", value: String(stats.community.unique_walkers) },
              { icon: <Route size={18} />, label: "Planned distance", value: formatDistance(stats.community.distance_meters) },
              { icon: <Clock3 size={18} />, label: "Estimated walking time", value: formatDuration(stats.community.duration_seconds) }
            ]}
          />
          <ProfileSection
            title="Reviews"
            items={[
              { icon: <MessageSquareText size={18} />, label: "Reviews left", value: String(stats.reviews.left_count) },
              { icon: <Star size={18} />, label: "Average left", value: formatRating(stats.reviews.left_average) },
              { icon: <MessageSquareText size={18} />, label: "Reviews on your tours", value: String(stats.reviews.owned_count) },
              { icon: <Star size={18} />, label: "Average on your tours", value: formatRating(stats.reviews.owned_average) }
            ]}
          />
        </>
      ) : null}
    </div>
  );
}

function ProfileSection({
  title,
  subtitle,
  items
}: {
  title: string;
  subtitle?: string;
  items: MetricItem[];
}) {
  return (
    <section className="profile-section">
      <header className="profile-section-heading">
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </header>
      <div className="metric-table" role="table" aria-label={title}>
        {items.map((item) => (
          <div className="metric-row" role="row" key={item.label}>
            <div className="metric-label" role="rowheader">
              <span className="metric-icon">{item.icon}</span>
              <span>{item.label}</span>
            </div>
            <strong className="metric-value" role="cell">{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatRating(rating: number | null): string {
  return rating === null ? "—" : `${rating.toFixed(1)} / 5`;
}
