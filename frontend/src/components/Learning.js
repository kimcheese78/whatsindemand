// Learning Tracker UI — a dashboard module listing the skills a user is
// learning (with market validation) and a reusable toggle for marking a gap
// skill "I'm learning this". Self-contained: talks to the API directly and
// takes callbacks as props to avoid a circular import with App.js.
import React, { useState, useEffect } from 'react';
import { GraduationCap, Check, Plus } from 'lucide-react';
import { Panel } from './ui';
import api from '../services/api';

const cx = (...xs) => xs.filter(Boolean).join(' ');

// Small toggle for a single skill the user doesn't have yet. Optimistic.
// `onAcquired` (optional) is called if the skill is later marked "have".
export function LearningToggle({ skillId, skillName, category, initialStatus = 'missing', onAcquired }) {
  const [status, setStatus] = useState(initialStatus); // 'missing' | 'learning' | 'have'
  const [busy, setBusy] = useState(false);

  const mark = async (next) => {
    if (busy) return;
    const prev = status;
    setStatus(next);
    setBusy(true);
    try {
      await api.setSkillStatus(skillId, next === 'missing' ? 'have' : next);
      if (next === 'have' && onAcquired) {
        onAcquired({ skill_id: skillId, name: skillName, category });
      }
    } catch {
      setStatus(prev); // revert on failure
    } finally {
      setBusy(false);
    }
  };

  if (status === 'have') {
    return <span className="inline-flex items-center gap-1 text-small text-accent-up"><Check className="w-3.5 h-3.5" />Added</span>;
  }
  if (status === 'learning') {
    return (
      <button onClick={() => mark('have')} disabled={busy}
        className="inline-flex items-center gap-1 text-small text-accent-warn hover:text-white transition-colors disabled:opacity-50">
        <GraduationCap className="w-3.5 h-3.5" />Learning · mark as have
      </button>
    );
  }
  return (
    <button onClick={() => mark('learning')} disabled={busy}
      className="inline-flex items-center gap-1 text-small text-ink-muted hover:text-white transition-colors disabled:opacity-50">
      <Plus className="w-3.5 h-3.5" />I'm learning this
    </button>
  );
}

// Dashboard module: the user's active learning list + progress. Renders nothing
// when empty, so it never adds hollow chrome.
export function LearningModule({ onAcquired }) {
  const [items, setItems] = useState(null);
  const [justAdded, setJustAdded] = useState(null); // celebratory copy

  useEffect(() => {
    let alive = true;
    api.getLearning()
      .then((d) => { if (alive) setItems(d.learning || []); })
      .catch(() => { if (alive) setItems([]); });
    return () => { alive = false; };
  }, []);

  if (!items || items.length === 0) return null;

  const markHave = async (skill) => {
    setItems((cur) => cur.filter((s) => s.skill_id !== skill.skill_id));
    setJustAdded(skill.name);
    try {
      await api.setSkillStatus(skill.skill_id, 'have');
      if (onAcquired) onAcquired({ skill_id: skill.skill_id, name: skill.name, category: skill.category });
    } catch {
      // put it back on failure
      setItems((cur) => [...cur, skill]);
      setJustAdded(null);
    }
  };

  return (
    <Panel tone="raised" pad="lg">
      <div className="flex items-center gap-2 mb-4">
        <GraduationCap className="w-4 h-4 text-accent-warn" />
        <div className="text-eyebrow uppercase text-ink-faint">Learning</div>
      </div>

      {justAdded && (
        <div className="mb-3 text-small text-accent-up">
          ✓ {justAdded} added to your skills — it now counts toward your matches and score.
        </div>
      )}

      <div className="space-y-3">
        {items.map((s) => (
          <div key={s.skill_id} className="flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="text-ink font-medium truncate">{s.name}</div>
              <div className="text-small text-ink-muted">
                {s.weeks_learning != null && (
                  <span>{s.weeks_learning === 0 ? 'Started this week' : `${s.weeks_learning}w in`}</span>
                )}
                {s.demand_pct != null && <span> · in {s.demand_pct}% of postings</span>}
                {s.growth_pct != null && (
                  <span className={cx(' · ', s.growth_pct >= 0 ? 'text-accent-up' : 'text-accent-down')}>
                    {s.growth_pct >= 0 ? '+' : ''}{s.growth_pct}% since you started
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => markHave(s)}
              className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 text-small font-medium border border-line-strong rounded-lg text-ink-muted hover:text-white hover:border-white/40 transition-colors"
            >
              <Check className="w-3.5 h-3.5" />Mark as have
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}
