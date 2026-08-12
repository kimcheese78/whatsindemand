// Design-system primitives. One source of truth for panel chrome, labels, stats, pills.
// Tone: data-newsroom on dark — quiet chrome, sharp corners, numbers do the talking.
import React from 'react';

const cx = (...xs) => xs.filter(Boolean).join(' ');

/**
 * Panel — the canonical container.
 * <Panel>{children}</Panel>
 * <Panel as="section" tone="raised" pad="lg" />
 */
export const Panel = ({ as: Tag = 'div', tone = 'default', pad = 'md', className, children, ...rest }) => {
  const bg = tone === 'raised' ? 'bg-surface-raised' : 'bg-surface';
  const padding = pad === 'sm' ? 'p-3' : pad === 'lg' ? 'p-6' : 'p-5';
  return (
    <Tag className={cx(bg, 'border border-line rounded-xl', padding, className)} {...rest}>
      {children}
    </Tag>
  );
};

/** Eyebrow — tiny uppercase section label that lives above panels and groups. */
export const Eyebrow = ({ className, children, ...rest }) => (
  <div className={cx('text-eyebrow uppercase text-ink-muted', className)} {...rest}>
    {children}
  </div>
);

/** Stat — a metric block: small label + big number. Used in the metric strip. */
export const Stat = ({ label, value, hint, tone = 'default', className }) => {
  const numTone =
    tone === 'up' ? 'text-accent-up' :
    tone === 'down' ? 'text-accent-down' :
    tone === 'muted' ? 'text-ink-faint' :
    'text-ink';
  return (
    <Panel pad="sm" className={className}>
      <div className="text-eyebrow uppercase text-ink-muted mb-1">{label}</div>
      <div className={cx('num text-h2', numTone)}>{value}</div>
      {hint && <div className="text-small text-ink-faint mt-1">{hint}</div>}
    </Panel>
  );
};

/** Pill — small status indicator with an optional dot. */
export const Pill = ({ tone = 'neutral', dot = true, children, className }) => {
  const styles = {
    up:      { wrap: 'bg-accent-up/15 text-accent-up',    dot: 'bg-accent-up' },
    down:    { wrap: 'bg-accent-down/15 text-accent-down', dot: 'bg-accent-down' },
    warn:    { wrap: 'bg-accent-warn/15 text-accent-warn', dot: 'bg-accent-warn' },
    neutral: { wrap: 'bg-line-strong text-ink-muted',     dot: 'bg-ink-muted' },
  }[tone];
  return (
    <span className={cx('inline-flex items-center gap-1.5 px-2 py-0.5 text-small font-medium', styles.wrap, className)}>
      {dot && <span className={cx('w-1.5 h-1.5', styles.dot)} />}
      {children}
    </span>
  );
};

/** Hero number — the single big number per panel (verdict, salary median). */
export const HeroNumber = ({ value, tone = 'default', className }) => {
  const t =
    tone === 'up'   ? 'text-accent-up'   :
    tone === 'down' ? 'text-accent-down' :
    tone === 'warn' ? 'text-accent-warn' :
    'text-ink';
  return <div className={cx('num text-display leading-none', t, className)}>{value}</div>;
};

/** Plain numeric span with tabular figures — for inline counts/percentages. */
export const Num = ({ children, className }) => (
  <span className={cx('num', className)}>{children}</span>
);

/** Minimal single-series SVG sparkline for trend cards. tone: up | down | default.
 *  Uses the accent-up/down palette; endpoint dot emphasizes the latest value. */
export const Sparkline = ({ data = [], tone = 'default', width = 96, height = 28, className }) => {
  if (!Array.isArray(data) || data.length < 2) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = max - min || 1;
  const stepX = width / (data.length - 1);
  const y = (v) => (height - 2) - ((v - min) / span) * (height - 4);
  const points = data.map((v, i) => `${(i * stepX).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const stroke =
    tone === 'up'   ? '#4ade80' :
    tone === 'down' ? '#f87171' :
    'rgba(255,255,255,0.45)';
  const lastX = (data.length - 1) * stepX;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden="true">
      <polyline points={points} fill="none" stroke={stroke} strokeWidth="1.5"
                strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX.toFixed(1)} cy={y(data[data.length - 1]).toFixed(1)} r="2" fill={stroke} />
    </svg>
  );
};
