'use client';
import type { RoomSummary, RoomTurn, SummaryItem } from '@/lib/api';
import { dateTime } from '@/lib/format';

const GROUPS: { key: 'agreements' | 'factual_disagreements' | 'value_disagreements' | 'concessions'; title: string; hint: string }[] = [
  { key: 'agreements', title: '共识点', hint: '双方都认可的部分' },
  { key: 'factual_disagreements', title: '事实分歧', hint: '可以查证的分歧' },
  { key: 'value_disagreements', title: '价值分歧', hint: '取决于看重什么，不是对错问题' },
  { key: 'concessions', title: '双方让步', hint: '有人调整了说法或接受了条件' },
];

/** The summary never picks a winner. Each line cites the exact sentence it came from. */
export function RoomSummaryCard({ summary, turns }: { summary: RoomSummary; turns: RoomTurn[] }) {
  return (
    <section className="card pad" aria-labelledby="sum-h">
      <div className="panel-title">
        <h2 id="sum-h" style={{ fontSize: 16, fontWeight: 600 }}>讨论总结</h2>
        <small>{dateTime(summary.generated_at)}</small>
      </div>
      <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>{summary.note}</p>
      <div style={{ display: 'grid', gap: 16 }}>
        {GROUPS.map((g) => {
          const items: SummaryItem[] = summary[g.key];
          if (!items.length) return null;
          return (
            <div key={g.key}>
              <h3 style={{ fontSize: 14, fontWeight: 600 }}>
                {g.title} <small className="muted" style={{ fontWeight: 400 }}>· {g.hint}</small>
              </h3>
              <ul className="list-plain" style={{ marginTop: 8, gap: 10 }}>
                {items.map((it, i) => (
                  <li key={i} style={{ display: 'block' }}>
                    <p style={{ fontSize: 14 }}>{it.text}</p>
                    <details className="quote-details">
                      <summary>对话中的原句（{it.quotes.length} 条）</summary>
                      <ul className="list-plain" style={{ marginTop: 6 }}>
                        {it.quotes.map((q, j) => (
                          <li key={j} style={{ display: 'block' }}>
                            <blockquote className="original" style={{ margin: 0, fontSize: 13 }}>
                              {q.quote}
                              <footer style={{ marginTop: 4, fontSize: 12, color: 'var(--muted)' }}>{turns[q.turn]?.name ?? `第 ${q.turn + 1} 条发言`}</footer>
                            </blockquote>
                          </li>
                        ))}
                      </ul>
                    </details>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
        {summary.open_questions.length > 0 && (
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>仍待查证</h3>
            <ul className="list-plain" style={{ marginTop: 8 }}>
              {summary.open_questions.map((q) => (
                <li key={q}>· {q}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
