// Position Score — the user's single weekly-tracked standing vs. their target
// role. Self-contained: fetches /api/position-score and renders the dashboard
// hero. Renders nothing until a snapshot exists, so it never shows hollow
// chrome. The history sparkline is a hand-rolled SVG polyline, matching the
// app's other charts (Recharts is a dependency but was never bundled; using it
// here would add ~87kB for a 12-point line).
import React, { useState, useEffect } from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';
import { Panel } from './ui';
import api from '../services/api';

const cx = (...xs) => xs.filter(Boolean).join(' ');

export function Sparkline({ points }) {
  if (!points || points.length < 2) return null;
  const w = 128, h = 48, pad = 5;
  const vals = points.map((p) => p.position_score ?? 0);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const step = (w - pad * 2) / (vals.length - 1);
  const coords = vals.map((v, i) => [
    pad + i * step,
    pad + (h - pad * 2) * (1 - (v - min) / range),
  ]);
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const [lx, ly] = coords[coords.length - 1];
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline points={line} fill="none" stroke="#4ade80" strokeWidth="2"
        strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lx} cy={ly} r="2.5" fill="#4ade80" />
    </svg>
  );
}

function scoreTone(score) {
  if (score >= 70) return 'text-accent-up';
  if (score >= 45) return 'text-ink';
  return 'text-accent-warn';
}

function DeltaBadge({ delta }) {
  if (delta === 0) {
    return <span className="text-small text-ink-muted">No change</span>;
  }
  const up = delta > 0;
  const Icon = up ? ArrowUp : ArrowDown;
  return (
    <span className={cx('inline-flex items-center gap-0.5 text-small font-medium',
      up ? 'text-accent-up' : 'text-accent-down')}>
      <Icon className="w-3.5 h-3.5" />{Math.abs(delta)} this week
    </span>
  );
}

export default function PositionScore() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    api.getPositionScore()
      .then((d) => { if (alive) setData(d); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!data || !data.current) return null;

  const { current, delta, history, tracking } = data;
  const driver = (current.drivers && current.drivers[0]) || null;

  return (
    <Panel tone="raised" pad="lg">
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="text-eyebrow uppercase text-ink-faint mb-2">Your Position Score</div>
          <div className="flex items-baseline gap-3">
            <span className={cx('num text-hero leading-none', scoreTone(current.position_score))}>
              {current.position_score}
            </span>
            <span className="text-ink-faint text-h2">/100</span>
          </div>

          <div className="mt-2">
            {tracking && delta != null
              ? <DeltaBadge delta={delta} />
              : <span className="text-small text-ink-muted">
                  Tracking begins this week — your history builds every Friday.
                </span>}
          </div>

          {tracking && driver && (
            <div className="mt-3 text-small text-ink-muted max-w-md">
              {delta != null && delta < 0 ? '↓ ' : ''}{driver.text}
            </div>
          )}
        </div>

        {/* Sparkline — only meaningful with 2+ points */}
        {history.length >= 2 && (
          <div className="shrink-0">
            <Sparkline points={history} />
          </div>
        )}
      </div>
    </Panel>
  );
}
