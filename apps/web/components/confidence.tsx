'use client';
import { useEffect, useState } from 'react';

type Saved = { before?: number; after?: number };
const key = (roomId: string) => `backcast:confidence:${roomId}`;

function read(roomId: string): Saved {
  try {
    const raw = JSON.parse(localStorage.getItem(key(roomId)) ?? '{}');
    const ok = (v: unknown) => (typeof v === 'number' && v >= 0 && v <= 100 ? v : undefined);
    return { before: ok(raw.before), after: ok(raw.after) };
  } catch {
    return {};
  }
}

/**
 * Self-rated confidence before and after a discussion. Stored only in this browser;
 * it records how the user felt, and says nothing about who was right.
 */
export function ConfidenceTracker({ roomId, userTurns, avatarReplies }: { roomId: string; userTurns: number; avatarReplies: number }) {
  const [saved, setSaved] = useState<Saved>({});
  const [beforeDraft, setBeforeDraft] = useState(50);
  const [afterDraft, setAfterDraft] = useState(50);
  useEffect(() => {
    const s = read(roomId);
    setSaved(s);
    if (s.before !== undefined) {
      setBeforeDraft(s.before);
      setAfterDraft(s.after ?? s.before);
    }
  }, [roomId]);

  function persist(next: Saved) {
    setSaved(next);
    try {
      localStorage.setItem(key(roomId), JSON.stringify(next));
    } catch {
      /* storage unavailable: the values still show for this visit */
    }
  }

  const beforeLocked = userTurns > 0;
  const canAfter = avatarReplies > 0;
  const delta = saved.before !== undefined && saved.after !== undefined ? saved.after - saved.before : undefined;

  return (
    <section className="card pad" aria-labelledby="conf-h">
      <div className="panel-title">
        <h2 id="conf-h" style={{ fontSize: 15, fontWeight: 600 }}>你的把握度</h2>
        <small>仅自评 · 只存在这台设备</small>
      </div>
      <div style={{ display: 'grid', gap: 14 }}>
        <div>
          <label htmlFor="conf-before" style={{ fontSize: 13, display: 'block', marginBottom: 6 }}>
            讨论前：我对自己立场有几成把握？ <b data-testid="conf-before-value">{saved.before ?? beforeDraft}</b>
          </label>
          <input id="conf-before" type="range" min={0} max={100} step={5} value={saved.before ?? beforeDraft} disabled={saved.before !== undefined || beforeLocked} onChange={(e) => setBeforeDraft(Number(e.target.value))} style={{ width: '100%' }} />
          {saved.before === undefined && (
            <div style={{ marginTop: 6 }}>
              {beforeLocked ? (
                <small className="muted">讨论已经开始，没有记录讨论前的把握度。</small>
              ) : (
                <button type="button" className="btn small" onClick={() => persist({ ...saved, before: beforeDraft })}>
                  记录讨论前的把握度
                </button>
              )}
            </div>
          )}
        </div>
        <div>
          <label htmlFor="conf-after" style={{ fontSize: 13, display: 'block', marginBottom: 6 }}>
            现在：我对自己立场有几成把握？ <b data-testid="conf-after-value">{saved.after ?? afterDraft}</b>
          </label>
          <input id="conf-after" type="range" min={0} max={100} step={5} value={saved.after ?? afterDraft} disabled={!canAfter} onChange={(e) => setAfterDraft(Number(e.target.value))} style={{ width: '100%' }} />
          <div style={{ marginTop: 6 }}>
            {canAfter ? (
              <button type="button" className="btn small" onClick={() => persist({ ...saved, after: afterDraft })}>
                记录现在的把握度
              </button>
            ) : (
              <small className="muted">分身回应之后才能记录。</small>
            )}
          </div>
        </div>
      </div>
      {delta !== undefined && (
        <p style={{ fontSize: 14, marginTop: 14 }} role="status" data-testid="conf-delta">
          {delta === 0 ? '把握度没有变化。' : `把握度${delta > 0 ? '上升' : '下降'}了 ${Math.abs(delta)} 点。`}
        </p>
      )}
      <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>这是你自己的主观评分。变化不代表分身说服了你，也不说明你的立场对错。</p>
    </section>
  );
}
