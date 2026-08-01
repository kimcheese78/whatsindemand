// B2B coach console — the /org screen for bootcamp career-services teams.
// Design principle: everything a coach needs at a glance on ONE screen —
// cohort health strip, client roster with score/gap/matches, and curriculum
// fit — with a drawer for per-client depth. No hunting through tabs.
//
// Standalone route (like CardScreen): auth comes from the stored token via
// the api service; users without an org get a create-org onboarding.
import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowUp, ArrowDown, ChevronDown, GraduationCap, Printer,
  RefreshCw, Sparkles, Users, X,
} from 'lucide-react';
import { Panel, Eyebrow } from '../ui';
import { Sparkline } from '../PositionScore';
import api from '../../services/api';

const cx = (...xs) => xs.filter(Boolean).join(' ');

const scoreTone = (s) =>
  s == null ? 'text-ink-faint' : s >= 70 ? 'text-accent-up' : s >= 45 ? 'text-ink' : 'text-accent-warn';

function Delta({ value }) {
  if (value == null) return null;
  if (value === 0) return <span className="text-small text-ink-faint">—</span>;
  const up = value > 0;
  const Icon = up ? ArrowUp : ArrowDown;
  return (
    <span className={cx('inline-flex items-center text-small font-medium',
      up ? 'text-accent-up' : 'text-accent-down')}>
      <Icon className="w-3 h-3" />{Math.abs(value)}
    </span>
  );
}

// ── Skill extraction input (shared by cohort curriculum + client resume) ────
function SkillExtractor({ label, hint, skills, setSkills }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const extract = async () => {
    if (text.trim().length < 30) { setError('Paste at least a paragraph.'); return; }
    setBusy(true); setError(null);
    try {
      const res = await api.extractSkillsFromText(text);
      const merged = [...skills];
      for (const s of res.skills || []) {
        if (!merged.some((m) => m.skill_id === s.skill_id)) merged.push(s);
      }
      setSkills(merged);
      setText('');
    } catch (e) {
      setError(e.message || 'Extraction failed');
    } finally { setBusy(false); }
  };

  return (
    <div>
      <label className="block text-eyebrow text-ink-faint mb-1 tracking-widest uppercase">{label}</label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={hint}
        rows={3}
        className="w-full px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-white"
      />
      <div className="flex items-center gap-3 mt-1.5">
        <button onClick={extract} disabled={busy}
          className="px-3 py-1.5 text-small font-medium bg-white/10 hover:bg-white/20 rounded-lg transition-colors disabled:opacity-50">
          {busy ? 'Extracting…' : 'Extract skills'}
        </button>
        {error && <span className="text-small text-accent-down">{error}</span>}
        <span className="text-small text-ink-faint">{skills.length} skills</span>
      </div>
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {skills.map((s) => (
            <span key={s.skill_id}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-small bg-white/10 rounded">
              {s.name}
              <button onClick={() => setSkills(skills.filter((x) => x.skill_id !== s.skill_id))}
                className="text-ink-faint hover:text-white"><X className="w-3 h-3" /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Client drawer (per-client depth + printable report) ─────────────────────
function ClientDrawer({ clientId, onClose, onDeleted }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setDetail(null);
    api.getOrgClientDetail(clientId)
      .then(setDetail)
      .catch((e) => setError(e.message || 'Failed to load client'));
  }, [clientId]);

  const remove = async () => {
    if (!window.confirm('Remove this client and their history?')) return;
    await api.deleteOrgClient(clientId);
    onDeleted();
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 print:bg-white print:relative"
      onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg h-full overflow-y-auto bg-zinc-900 border-l border-line p-6 print:max-w-none print:border-0"
      >
        {error && <div className="text-accent-down text-sm">{error}</div>}
        {!detail && !error && <div className="text-ink-muted text-sm">Loading client…</div>}
        {detail && (
          <>
            <div className="flex items-start justify-between mb-6 print:mb-4">
              <div>
                <div className="text-h2 font-medium">{detail.client.display_name}</div>
                <div className="text-small text-ink-muted">
                  {detail.client.target_role}
                  {detail.client.seniority ? ` · ${detail.client.seniority}` : ''}
                </div>
              </div>
              <div className="flex items-center gap-2 print:hidden">
                <button onClick={() => window.print()} title="Print report"
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                  <Printer className="w-4 h-4" />
                </button>
                <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Score */}
            <Panel tone="raised" className="mb-4">
              <div className="flex items-center justify-between">
                <div>
                  <Eyebrow className="mb-1">Position Score</Eyebrow>
                  <span className={cx('num text-display leading-none', scoreTone(detail.score.current))}>
                    {detail.score.current ?? '—'}
                  </span>
                  <span className="text-ink-faint text-sm ml-1">/100</span>
                </div>
                {detail.score.history.length >= 2 && <Sparkline points={detail.score.history} />}
              </div>
              {detail.score.drivers.length > 0 && (
                <div className="mt-3 space-y-1">
                  {detail.score.drivers.slice(0, 3).map((d, i) => (
                    <div key={i} className="text-small text-ink-muted">· {d.text}</div>
                  ))}
                </div>
              )}
            </Panel>

            {/* Gap */}
            {detail.gap && (
              <Panel className="mb-4">
                <div className="flex items-baseline justify-between mb-2">
                  <Eyebrow>Skill gap</Eyebrow>
                  <span className="text-small text-ink-muted">
                    market match <span className="num text-ink">{Math.round(detail.gap.match_score)}%</span>
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {detail.gap.top_missing.map((s) => (
                    <span key={s.skill_id}
                      className="px-2 py-0.5 text-small border border-accent-warn/40 text-accent-warn rounded">
                      {s.name} <span className="text-ink-faint">{Math.round(s.demand)}%</span>
                    </span>
                  ))}
                </div>
              </Panel>
            )}

            {/* Matched jobs */}
            <Panel className="mb-4">
              <div className="flex items-baseline justify-between mb-2">
                <Eyebrow>Matched jobs</Eyebrow>
                <span className="text-small text-ink-muted">
                  <span className="num text-ink">{detail.matched_jobs.total}</span> total
                  {detail.matched_jobs.new_this_week > 0 && (
                    <span className="text-accent-up"> · {detail.matched_jobs.new_this_week} new</span>
                  )}
                </span>
              </div>
              <div className="space-y-2">
                {detail.matched_jobs.top.slice(0, 6).map((j) => (
                  <a key={j.id} href={j.source_url || '#'} target="_blank" rel="noopener noreferrer"
                    className="flex items-center justify-between gap-3 text-sm hover:bg-white/5 -mx-2 px-2 py-1 rounded">
                    <span className="truncate">{j.title} <span className="text-ink-faint">· {j.company}</span></span>
                    <span className={cx('num shrink-0', scoreTone(Math.round(j.match_pct * 100)))}>
                      {Math.round(j.match_pct * 100)}%
                    </span>
                  </a>
                ))}
                {detail.matched_jobs.top.length === 0 && (
                  <div className="text-small text-ink-faint">No matches yet.</div>
                )}
              </div>
            </Panel>

            {/* Skills */}
            <Panel className="mb-4">
              <Eyebrow className="mb-2">Skills ({detail.skills.have.length})</Eyebrow>
              <div className="flex flex-wrap gap-1.5">
                {detail.skills.have.map((s) => (
                  <span key={s.skill_id} className="px-2 py-0.5 text-small bg-accent-up/15 text-accent-up rounded">
                    {s.name}
                  </span>
                ))}
              </div>
              {detail.skills.learning.length > 0 && (
                <>
                  <Eyebrow className="mt-3 mb-2">Learning</Eyebrow>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.skills.learning.map((s) => (
                      <span key={s.skill_id} className="px-2 py-0.5 text-small border border-line-strong text-ink-muted rounded">
                        <GraduationCap className="w-3 h-3 inline mr-1" />{s.name}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </Panel>

            <button onClick={remove}
              className="text-small text-accent-down hover:underline print:hidden">
              Remove client
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── Add-client modal ────────────────────────────────────────────────────────
function AddClientModal({ cohort, roles, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState(cohort?.target_role || '');
  const [seniority, setSeniority] = useState('entry');
  const [skills, setSkills] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    if (!name.trim()) { setError('Name is required.'); return; }
    if (!role) { setError('Target role is required.'); return; }
    setBusy(true); setError(null);
    try {
      await api.createOrgClient({
        display_name: name.trim(), email: email.trim() || null,
        target_role: role, seniority,
        cohort_id: cohort?.id ?? null,
        skill_ids: skills.map((s) => s.skill_id),
      });
      onCreated();
    } catch (e) {
      setError(e.message || 'Failed to create client');
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-zinc-900 border border-line rounded-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="text-h2 font-medium">Add client</div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-lg"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name *"
              className="px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none focus:border-white" />
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email (optional)"
              className="px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none focus:border-white" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select value={role} onChange={(e) => setRole(e.target.value)}
              className="px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none">
              <option value="">Target role *</option>
              {roles.map((r) => <option key={r.id} value={r.title}>{r.title}</option>)}
            </select>
            <select value={seniority} onChange={(e) => setSeniority(e.target.value)}
              className="px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none">
              <option value="entry">Entry</option><option value="mid">Mid</option>
              <option value="senior">Senior</option><option value="lead">Lead</option>
            </select>
          </div>
          <SkillExtractor
            label="Skills — paste their resume"
            hint="Paste the client's resume text; we'll extract their skills."
            skills={skills} setSkills={setSkills}
          />
          {error && <div className="text-small text-accent-down">{error}</div>}
          <button onClick={save} disabled={busy}
            className="w-full py-2.5 bg-white text-black text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50">
            {busy ? 'Creating + scoring…' : 'Add client'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Cohort setup (create/edit with curriculum) ──────────────────────────────
function CohortForm({ roles, existing, onClose, onSaved }) {
  const [name, setName] = useState(existing?.name || '');
  const [role, setRole] = useState(existing?.target_role || '');
  const [skills, setSkills] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    if (!name.trim() || !role) { setError('Name and target role are required.'); return; }
    setBusy(true); setError(null);
    const payload = {
      name: name.trim(), target_role: role,
      ...(skills.length ? { curriculum_skill_ids: skills.map((s) => s.skill_id) } : {}),
    };
    try {
      if (existing) await api.updateCohort(existing.id, payload);
      else await api.createCohort(payload);
      onSaved();
    } catch (e) {
      setError(e.message || 'Failed to save cohort'); setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-zinc-900 border border-line rounded-xl p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="text-h2 font-medium">{existing ? 'Edit cohort' : 'New cohort'}</div>
          <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-lg"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Cohort name * (e.g. Fall 2026)"
              className="px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none focus:border-white" />
            <select value={role} onChange={(e) => setRole(e.target.value)}
              className="px-3 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none">
              <option value="">Target role *</option>
              {roles.map((r) => <option key={r.id} value={r.title}>{r.title}</option>)}
            </select>
          </div>
          <SkillExtractor
            label="Curriculum — paste your syllabus"
            hint="Paste the program syllabus / curriculum outline; we'll extract the skills it teaches and compare them against live market demand."
            skills={skills} setSkills={setSkills}
          />
          {error && <div className="text-small text-accent-down">{error}</div>}
          <button onClick={save} disabled={busy}
            className="w-full py-2.5 bg-white text-black text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50">
            {busy ? 'Saving…' : existing ? 'Save cohort' : 'Create cohort'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Curriculum-fit panel ────────────────────────────────────────────────────
function CurriculumFit({ cohortId, coveragePct }) {
  const [fit, setFit] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setFit(null); setError(null);
    api.getCurriculumFit(cohortId).then(setFit).catch((e) => setError(e.message));
  }, [cohortId]);

  if (error) {
    return (
      <Panel>
        <Eyebrow className="mb-1">Curriculum vs market</Eyebrow>
        <div className="text-small text-ink-muted">{error}</div>
      </Panel>
    );
  }
  if (!fit) {
    return <Panel><Eyebrow className="mb-1">Curriculum vs market</Eyebrow>
      <div className="text-small text-ink-muted">Analyzing curriculum against live postings…</div></Panel>;
  }

  return (
    <Panel>
      <div className="flex items-baseline justify-between mb-3">
        <Eyebrow>Curriculum vs market · {fit.role.title}</Eyebrow>
        <span className="text-small text-ink-muted">
          <span className={cx('num text-h2', scoreTone(Math.round(fit.coverage_pct)))}>
            {Math.round(fit.coverage_pct)}%
          </span> demand coverage · {fit.jobs_analyzed.toLocaleString()} live postings
        </span>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="text-small font-medium text-accent-warn mb-1.5">
            Missing high-demand skills ({fit.missing.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {fit.missing.map((s) => (
              <span key={s.skill_id} className="px-2 py-0.5 text-small border border-accent-warn/40 text-accent-warn rounded">
                {s.name} <span className="opacity-70">{Math.round(s.demand)}%</span>
              </span>
            ))}
            {fit.missing.length === 0 && <span className="text-small text-ink-faint">None — full coverage of high-demand skills.</span>}
          </div>
        </div>
        <div>
          <div className="text-small font-medium text-ink mb-1.5">
            Emerging (fast-growing, not taught)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {fit.emerging.map((s) => (
              <span key={s.skill_id} className="px-2 py-0.5 text-small bg-white/10 rounded">
                {s.name} <span className="text-accent-up">+{Math.round(s.growth_pct)}%</span>
              </span>
            ))}
            {fit.emerging.length === 0 && <span className="text-small text-ink-faint">Nothing surging that you don't already teach.</span>}
          </div>
        </div>
      </div>
    </Panel>
  );
}

// ── Main console ────────────────────────────────────────────────────────────
export default function OrgConsole() {
  const [org, setOrg] = useState(undefined);       // undefined = loading
  const [cohorts, setCohorts] = useState([]);
  const [activeCohort, setActiveCohort] = useState(null);
  const [rollup, setRollup] = useState(null);
  const [roles, setRoles] = useState([]);
  const [drawerClient, setDrawerClient] = useState(null);
  const [showAddClient, setShowAddClient] = useState(false);
  const [showCohortForm, setShowCohortForm] = useState(false);
  const [editCohort, setEditCohort] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [orgName, setOrgName] = useState('');
  const [authError, setAuthError] = useState(false);

  const loadOrg = useCallback(() => {
    api.getOrg()
      .then((d) => setOrg(d.organization))
      .catch(() => setAuthError(true));
  }, []);

  useEffect(() => { loadOrg(); }, [loadOrg]);

  useEffect(() => {
    if (!org) return;
    api.getCohorts().then((d) => {
      setCohorts(d.cohorts);
      setActiveCohort((cur) => cur ?? d.cohorts[0] ?? null);
    });
    api.getAvailableRoles(10).then((d) => setRoles(d.roles || [])).catch(() => {});
  }, [org]);

  const loadRollup = useCallback(() => {
    if (!activeCohort) { setRollup(null); return; }
    setRollup(null);
    api.getCohortRollup(activeCohort.id).then(setRollup).catch(() => setRollup({ error: true }));
  }, [activeCohort]);

  useEffect(() => { loadRollup(); }, [loadRollup]);

  const refresh = async () => {
    setRefreshing(true);
    try { await api.refreshCohort(activeCohort.id); await loadRollup(); }
    finally { setRefreshing(false); }
  };

  // ── States: signed out / loading / no org ────────────────────────────────
  if (authError) {
    return (
      <div className="min-h-screen bg-zinc-900 text-white flex flex-col items-center justify-center gap-4">
        <p className="text-ink-muted text-sm">Sign in to access the coach console.</p>
        <a href="/login" className="text-sm text-white underline">Sign in →</a>
      </div>
    );
  }
  if (org === undefined) {
    return <div className="min-h-screen bg-zinc-900 text-white flex items-center justify-center text-ink-muted text-sm">Loading console…</div>;
  }
  if (org === null) {
    return (
      <div className="min-h-screen bg-zinc-900 text-white flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          <h1 className="text-3xl font-semibold tracking-tight mb-2">SET UP YOUR TEAM</h1>
          <p className="text-ink-muted mb-6 text-sm">
            Track every client's market position, skill gaps, and live job matches — in one view.
          </p>
          <input value={orgName} onChange={(e) => setOrgName(e.target.value)}
            placeholder="Organization name (e.g. Lambda Career Services)"
            className="w-full px-4 py-3 bg-surface border border-line-strong rounded-lg text-sm mb-3 focus:outline-none focus:border-white" />
          <button
            onClick={() => api.createOrg(orgName).then(loadOrg)}
            disabled={!orgName.trim()}
            className="w-full py-3 bg-white text-black text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-40">
            Create organization
          </button>
        </div>
      </div>
    );
  }

  const stats = rollup?.stats;

  return (
    <div className="min-h-screen bg-zinc-900 text-white">
      {/* Header */}
      <div className="border-b border-line bg-zinc-950 print:hidden">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <a href="/" className="text-sm font-medium tracking-widest shrink-0">WhatsInDemand</a>
            <span className="text-ink-faint">/</span>
            <span className="text-sm text-ink-muted truncate">{org.name}</span>
          </div>
          <div className="flex items-center gap-2">
            {cohorts.length > 0 && (
              <div className="relative">
                <select
                  value={activeCohort?.id || ''}
                  onChange={(e) => setActiveCohort(cohorts.find((c) => c.id === +e.target.value) || null)}
                  className="appearance-none pl-3 pr-8 py-2 bg-surface border border-line-strong rounded-lg text-sm focus:outline-none">
                  {cohorts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <ChevronDown className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-ink-muted" />
              </div>
            )}
            <button onClick={() => { setEditCohort(null); setShowCohortForm(true); }}
              className="px-3 py-2 text-sm border border-line-strong rounded-lg hover:bg-surface transition-colors">
              + Cohort
            </button>
            {activeCohort && (
              <button onClick={() => setShowAddClient(true)}
                className="px-3 py-2 text-sm font-medium bg-white text-black rounded-lg hover:bg-gray-200 transition-colors">
                + Client
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-5">
        {!activeCohort ? (
          <Panel pad="lg" className="text-center">
            <Users className="w-8 h-8 text-ink-faint mx-auto mb-3" />
            <div className="font-medium mb-1">Create your first cohort</div>
            <div className="text-small text-ink-muted max-w-md mx-auto">
              A cohort groups clients working toward the same role — and lets us score
              your curriculum against live market demand.
            </div>
          </Panel>
        ) : (
          <>
            {/* Stat strip — the at-a-glance cohort health row */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Panel pad="sm">
                <Eyebrow className="mb-1">Clients</Eyebrow>
                <div className="num text-h2">{stats ? stats.clients : '…'}</div>
              </Panel>
              <Panel pad="sm">
                <Eyebrow className="mb-1">Avg score</Eyebrow>
                <div className="flex items-baseline gap-2">
                  <span className={cx('num text-h2', scoreTone(stats?.avg_score))}>
                    {stats?.avg_score ?? '—'}
                  </span>
                  {stats?.avg_delta != null && <Delta value={stats.avg_delta} />}
                </div>
              </Panel>
              <Panel pad="sm">
                <Eyebrow className="mb-1">New matches</Eyebrow>
                <div className="num text-h2 text-accent-up">{stats?.new_matches_this_week ?? '—'}</div>
              </Panel>
              <Panel pad="sm">
                <Eyebrow className="mb-1">Learning</Eyebrow>
                <div className="num text-h2">{stats?.learning_total ?? '—'}</div>
              </Panel>
              <Panel pad="sm">
                <Eyebrow className="mb-1">Curriculum fit</Eyebrow>
                <div className={cx('num text-h2', scoreTone(stats?.curriculum_coverage_pct))}>
                  {stats?.curriculum_coverage_pct != null ? `${Math.round(stats.curriculum_coverage_pct)}%` : '—'}
                </div>
              </Panel>
            </div>

            {/* Roster — one row per client, everything scannable */}
            <Panel pad="sm" className="overflow-x-auto">
              <div className="flex items-center justify-between px-2 pt-1 pb-3">
                <Eyebrow>Client roster</Eyebrow>
                <button onClick={refresh} disabled={refreshing}
                  className="inline-flex items-center gap-1.5 text-small text-ink-muted hover:text-white transition-colors disabled:opacity-50 print:hidden">
                  <RefreshCw className={cx('w-3.5 h-3.5', refreshing && 'animate-spin')} />
                  {refreshing ? 'Rescoring…' : 'Rescore now'}
                </button>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-eyebrow uppercase text-ink-faint text-left border-b border-line">
                    <th className="px-2 py-2 font-medium">Client</th>
                    <th className="px-2 py-2 font-medium">Score</th>
                    <th className="px-2 py-2 font-medium">Δ wk</th>
                    <th className="px-2 py-2 font-medium">Top gap</th>
                    <th className="px-2 py-2 font-medium text-right">Job matches</th>
                    <th className="px-2 py-2 font-medium text-right">Learning</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {(rollup?.clients || []).map((c) => (
                    <tr key={c.id} onClick={() => setDrawerClient(c.id)}
                      className="cursor-pointer hover:bg-white/5 transition-colors">
                      <td className="px-2 py-2.5">
                        <div className="font-medium">{c.display_name}</div>
                        <div className="text-small text-ink-faint">{c.target_role}{c.seniority ? ` · ${c.seniority}` : ''}</div>
                      </td>
                      <td className={cx('px-2 py-2.5 num text-base', scoreTone(c.score))}>{c.score ?? '—'}</td>
                      <td className="px-2 py-2.5"><Delta value={c.delta} /></td>
                      <td className="px-2 py-2.5">
                        {c.top_gap
                          ? <span className="px-2 py-0.5 text-small border border-accent-warn/40 text-accent-warn rounded">{c.top_gap}</span>
                          : <span className="text-ink-faint text-small">—</span>}
                      </td>
                      <td className="px-2 py-2.5 text-right num">
                        {c.matched_jobs ?? '—'}
                        {c.new_matches > 0 && <span className="text-accent-up text-small"> +{c.new_matches}</span>}
                      </td>
                      <td className="px-2 py-2.5 text-right num">{c.learning_count || '—'}</td>
                    </tr>
                  ))}
                  {rollup && (rollup.clients || []).length === 0 && (
                    <tr><td colSpan={6} className="px-2 py-8 text-center text-ink-muted text-sm">
                      No clients yet — add your first client to see their market position.
                    </td></tr>
                  )}
                  {!rollup && (
                    <tr><td colSpan={6} className="px-2 py-8 text-center text-ink-muted text-sm">Loading roster…</td></tr>
                  )}
                </tbody>
              </table>
            </Panel>

            {/* Curriculum vs market */}
            {activeCohort.curriculum_skill_ids?.length > 0 ? (
              <CurriculumFit cohortId={activeCohort.id} />
            ) : (
              <Panel>
                <div className="flex items-center justify-between">
                  <div>
                    <Eyebrow className="mb-1">Curriculum vs market</Eyebrow>
                    <div className="text-small text-ink-muted">
                      Paste your syllabus to see how it covers live market demand — and what's missing.
                    </div>
                  </div>
                  <button onClick={() => { setEditCohort(activeCohort); setShowCohortForm(true); }}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-line-strong rounded-lg hover:bg-surface transition-colors shrink-0">
                    <Sparkles className="w-4 h-4" /> Add curriculum
                  </button>
                </div>
              </Panel>
            )}
          </>
        )}
      </div>

      {/* Overlays */}
      {drawerClient && (
        <ClientDrawer clientId={drawerClient}
          onClose={() => setDrawerClient(null)}
          onDeleted={() => { setDrawerClient(null); loadRollup(); }} />
      )}
      {showAddClient && activeCohort && (
        <AddClientModal cohort={activeCohort} roles={roles}
          onClose={() => setShowAddClient(false)}
          onCreated={() => { setShowAddClient(false); loadRollup(); }} />
      )}
      {showCohortForm && (
        <CohortForm roles={roles} existing={editCohort}
          onClose={() => setShowCohortForm(false)}
          onSaved={() => {
            setShowCohortForm(false);
            api.getCohorts().then((d) => {
              setCohorts(d.cohorts);
              if (editCohort) {
                const updated = d.cohorts.find((c) => c.id === editCohort.id);
                if (updated) setActiveCohort(updated);
              } else {
                setActiveCohort(d.cohorts[0] ?? null);
              }
            });
          }} />
      )}
    </div>
  );
}
