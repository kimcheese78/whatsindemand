// Matched Jobs — live postings ranked by how much of each job's skill set the
// user already has. Self-contained: talks to the API directly and takes nav
// callbacks as props so it can live outside App.js without a circular import.
import React, { useState, useEffect } from 'react';
import { MapPin, ChevronDown, Sparkles } from 'lucide-react';
import { Panel, Pill } from './ui';
import api from '../services/api';

const cx = (...xs) => xs.filter(Boolean).join(' ');

function relativeDate(iso) {
  if (!iso) return null;
  const days = Math.floor((Date.now() - new Date(iso)) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function matchTone(pct) {
  if (pct >= 0.85) return 'text-accent-up';
  if (pct >= 0.7) return 'text-ink';
  return 'text-ink-muted';
}

const locationLabel = (loc) => {
  if (!loc) return null;
  if (loc.is_remote) return 'Remote';
  return [loc.city, loc.state || loc.country].filter(Boolean).join(', ') || null;
};

function MatchRow({ job }) {
  const [open, setOpen] = useState(false);
  const loc = locationLabel(job.location);
  const posted = relativeDate(job.posted_at);

  return (
    <Panel pad="sm" className="hover:border-line-strong transition-colors">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-start gap-4 text-left"
      >
        {/* Logo */}
        <div className="w-10 h-10 relative shrink-0 mt-0.5">
          <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center absolute inset-0">
            <span className="text-sm font-bold text-ink-muted">{job.company?.[0]}</span>
          </div>
          {job.logo_url && (
            <img
              src={job.logo_url}
              alt={job.company}
              className="w-10 h-10 rounded-lg object-contain bg-surface p-1 relative"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          )}
        </div>

        {/* Title / company / meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-ink truncate">{job.title}</span>
            {job.new_this_week && <Pill tone="up" dot={false}>NEW</Pill>}
          </div>
          <div className="text-small text-ink-muted mt-0.5 truncate">{job.company}</div>
          <div className="flex items-center gap-3 mt-1.5 text-small text-ink-faint">
            {loc && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="w-3 h-3" /> {loc}
              </span>
            )}
            {job.seniority_level && <span className="capitalize">{job.seniority_level}</span>}
            {posted && <span>{posted}</span>}
          </div>
        </div>

        {/* Match % — the visual anchor */}
        <div className="shrink-0 text-right">
          <div className={cx('num text-h2 leading-none', matchTone(job.match_pct))}>
            {Math.round(job.match_pct * 100)}%
          </div>
          <div className="text-eyebrow uppercase text-ink-faint mt-1">match</div>
        </div>
        <ChevronDown
          className={cx('w-4 h-4 text-ink-faint shrink-0 mt-1 transition-transform', open && 'rotate-180')}
        />
      </button>

      {open && (
        <div className="mt-4 pt-4 border-t border-line grid sm:grid-cols-2 gap-4">
          <div>
            <div className="text-eyebrow uppercase text-ink-faint mb-2">
              You have ({job.matched_skills.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {job.matched_skills.length === 0 && (
                <span className="text-small text-ink-faint">None</span>
              )}
              {job.matched_skills.map((s) => (
                <span key={s} className="px-2 py-0.5 text-small bg-accent-up/15 text-accent-up rounded">
                  {s}
                </span>
              ))}
            </div>
          </div>
          <div>
            <div className="text-eyebrow uppercase text-ink-faint mb-2">
              Missing ({job.missing_skills.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {job.missing_skills.length === 0 && (
                <span className="text-small text-ink-faint">Nothing — full match</span>
              )}
              {job.missing_skills.map((s) => (
                <span key={s} className="px-2 py-0.5 text-small border border-line-strong text-ink-muted rounded">
                  {s}
                </span>
              ))}
            </div>
          </div>
          {job.source_url && (
            <a
              href={job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="sm:col-span-2 inline-flex items-center justify-center gap-1.5 py-2.5 bg-white text-black text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors"
            >
              View posting ↗
            </a>
          )}
        </div>
      )}
    </Panel>
  );
}

// Compact dashboard card: "N new matches this week" linking to the Jobs tab.
// Renders nothing until it has matches to show, so it never adds hollow chrome.
export function MatchedJobsSummaryCard({ onView }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    let alive = true;
    api.getMatchedJobsSummary()
      .then((d) => { if (alive) setSummary(d); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!summary || !summary.total_matches) return null;

  const { total_matches, new_this_week, top_match } = summary;
  const headline = new_this_week > 0
    ? `${new_this_week} new ${new_this_week === 1 ? 'match' : 'matches'} this week`
    : `${total_matches} ${total_matches === 1 ? 'job matches' : 'jobs match'} your skills`;

  return (
    <button onClick={onView} className="w-full text-left">
      <Panel tone="raised" className="hover:border-line-strong transition-colors flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-accent-up/15 flex items-center justify-center shrink-0">
          <Sparkles className="w-5 h-5 text-accent-up" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-ink">{headline}</div>
          {top_match && (
            <div className="text-small text-ink-muted truncate">
              Top: {top_match.title} · {Math.round(top_match.match_pct * 100)}% match
            </div>
          )}
        </div>
        <span className="text-small text-ink-muted shrink-0">View all →</span>
      </Panel>
    </button>
  );
}

export default function MatchedJobs() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    api.getMatchedJobs()
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setError(e.message || 'Failed to load matches'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  if (loading) {
    return <div className="text-ink-muted text-sm py-12 text-center">Finding jobs that match your skills…</div>;
  }
  if (error) {
    return <div className="text-accent-down text-sm py-12 text-center">{error}</div>;
  }

  const matches = data?.matches || [];

  if (matches.length === 0) {
    return (
      <Panel pad="lg" className="text-center">
        <div className="text-ink font-medium mb-1">No strong matches yet</div>
        <div className="text-small text-ink-muted max-w-md mx-auto">
          We surface postings where you already have most of the required skills.
          Add more skills to your profile, or check back as new jobs are scraped each week.
        </div>
      </Panel>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <div className="text-sm text-ink-muted">
          <span className="text-white font-medium">{data.total_matches}</span> matching{' '}
          {data.total_matches === 1 ? 'job' : 'jobs'}
          {data.new_this_week > 0 && (
            <span> • <span className="text-accent-up">{data.new_this_week} new this week</span></span>
          )}
        </div>
      </div>

      <div className="space-y-3">
        {matches.map((job) => <MatchRow key={job.id} job={job} />)}
      </div>
    </div>
  );
}
