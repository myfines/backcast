'use client';
import type { Persona, RoomTurn } from '@/lib/api';

type Row = { key: string; quote: string; count: number; inProfile: boolean };

/** Counts how often each source quote was cited by the author avatar. Counts show grounding, not argument quality. */
export function usageRows(persona: Persona | undefined, turns: RoomTurn[]): Row[] {
  const rows = new Map<string, Row>();
  const keyOf = (sourceId: string, quote: string) => `${sourceId}\u0000${quote}`;
  for (const f of persona?.facets ?? [])
    for (const q of f.quotes) {
      const key = keyOf(q.source_id, q.quote);
      if (!rows.has(key)) rows.set(key, { key, quote: q.quote, count: 0, inProfile: true });
    }
  for (const t of turns) {
    if (t.kind !== 'author_avatar') continue;
    for (const q of t.quotes ?? []) {
      const key = keyOf(q.source_id, q.quote);
      const row = rows.get(key) ?? { key, quote: q.quote, count: 0, inProfile: false };
      row.count += 1;
      rows.set(key, row);
    }
  }
  return [...rows.values()].sort((a, b) => b.count - a.count);
}

export function QuoteUsage({ persona, turns }: { persona?: Persona; turns: RoomTurn[] }) {
  const rows = usageRows(persona, turns);
  if (!rows.length) return null;
  const max = Math.max(1, ...rows.map((r) => r.count));
  const used = rows.filter((r) => r.count > 0);
  const total = used.reduce((s, r) => s + r.count, 0);
  const outside = rows.filter((r) => !r.inProfile && r.count > 0).length;
  const avatarReplies = turns.filter((t) => t.kind === 'author_avatar').length;
  return (
    <section className="card pad" aria-labelledby="usage-h">
      <div className="panel-title">
        <h2 id="usage-h" style={{ fontSize: 15, fontWeight: 600 }}>原话使用情况</h2>
        <small>{avatarReplies} 次分身回应</small>
      </div>
      <p style={{ fontSize: 13 }} data-testid="usage-summary">
        画像收录 {rows.filter((r) => r.inProfile).length} 条原话，本场引用了 {used.length} 条，共 {total} 次
        {outside > 0 ? `（其中 ${outside} 条不在画像里）` : ''}。
      </p>
      <ul className="list-plain" style={{ marginTop: 10, gap: 10 }}>
        {rows.map((r) => (
          <li key={r.key} style={{ display: 'block' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 10, alignItems: 'baseline', fontSize: 12 }}>
              <span style={{ overflowWrap: 'anywhere' }} className={r.count ? '' : 'muted'}>
                “{r.quote.length > 44 ? `${r.quote.slice(0, 44)}……` : r.quote}”
              </span>
              <b style={{ fontVariantNumeric: 'tabular-nums', color: r.count ? 'var(--ink-2)' : 'var(--faint)' }}>{r.count ? `${r.count} 次` : '未引用'}</b>
            </div>
            <div className="meter-track" role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={r.count} aria-label={`引用次数：${r.quote.slice(0, 20)}`} style={{ marginTop: 4 }}>
              <div className="meter-fill" style={{ width: `${(r.count / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>次数只说明分身的话有多少依据，不说明论证是否正确，也不等于对原文的忠实解读。</p>
    </section>
  );
}
