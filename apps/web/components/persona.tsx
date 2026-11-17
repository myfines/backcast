'use client';
import { ExternalLink } from 'lucide-react';
import type { Persona, SourceQuote } from '@/lib/api';
import { Notice } from './ui';

const FACET_LABEL: Record<string, string> = { view: '观点', value: '价值取向', principle: '原则', style: '表达风格' };

/** The warning that must stay visible wherever an AI persona of a real author appears. */
export function SimulationNotice() {
  return (
    <Notice tone="warn" title="这是 AI 依据公开文字生成的模拟，不是作者本人">
      分身的回答只是对已收集材料的推演，可能曲解原意，也不代表本人真实立场。每条回应都附有所依据的原话，请展开核对。
    </Notice>
  );
}

/** Quotes a reply relies on, linked to the document they came from. */
export function QuoteList({ quotes, persona }: { quotes: SourceQuote[]; persona?: Persona }) {
  if (!quotes.length) return null;
  return (
    <details className="quote-details">
      <summary>所依据的原话（{quotes.length} 条）</summary>
      <ul className="list-plain" style={{ marginTop: 8 }}>
        {quotes.map((q, i) => {
          const doc = persona?.documents.find((d) => d.id === q.source_id);
          return (
            <li key={`${q.source_id}-${i}`} style={{ display: 'block' }}>
              <blockquote className="original" style={{ margin: 0, fontSize: 13 }}>
                {q.quote}
                {doc && (
                  <footer style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>
                    <a href={doc.url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
                      {doc.title || doc.url} <ExternalLink size={11} aria-hidden style={{ display: 'inline' }} />
                    </a>
                  </footer>
                )}
              </blockquote>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

export function PersonaCard({ persona }: { persona: Persona }) {
  const cov = persona.coverage;
  return (
    <section className="card pad" aria-labelledby="persona-h">
      <div className="panel-title">
        <h2 id="persona-h" style={{ fontSize: 16, fontWeight: 600 }}>{persona.label}</h2>
        <span className="tag">AI 分身</span>
      </div>
      <ul className="list-plain" style={{ gap: 14 }}>
        {persona.facets.map((f, i) => (
          <li key={i} style={{ display: 'block' }}>
            <span className="tag outline">{FACET_LABEL[f.kind] ?? f.kind}</span>
            <p style={{ fontSize: 14, marginTop: 6 }}>{f.description}</p>
            <QuoteList quotes={f.quotes} persona={persona} />
          </li>
        ))}
      </ul>
      {persona.unknowns.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '16px 0 8px' }}>还不了解的部分</h3>
          <ul className="list-plain">
            {persona.unknowns.map((u) => (
              <li key={u} className="muted">· {u}</li>
            ))}
          </ul>
        </>
      )}
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: '16px 0 8px' }}>材料范围</h3>
      <dl className="kv" style={{ marginTop: 0 }}>
        <dt>画像所用材料</dt>
        <dd>{cov?.profiled_documents ?? persona.documents.length} 份</dd>
        <dt>是否完整人格</dt>
        <dd>{cov?.complete_personality ? '是' : '否'}</dd>
        <dt>作者身份</dt>
        <dd>{cov?.author_identity_verified ? '已核验' : '未独立核验'}</dd>
      </dl>
      {cov?.input_authorship && <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>署名来源：{cov.input_authorship}</p>}
      {persona.snapshot_note && <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>{persona.snapshot_note}</p>}
      <ul className="list-plain" style={{ marginTop: 10 }}>
        {persona.documents.map((d) => (
          <li key={d.id}>
            <a href={d.url} target="_blank" rel="noreferrer noopener" style={{ overflowWrap: 'anywhere', fontSize: 13 }}>
              {d.title || d.url} <ExternalLink size={11} aria-hidden style={{ display: 'inline' }} />
            </a>
            {d.excerpt_note && <small className="muted"> · {d.excerpt_note}</small>}
          </li>
        ))}
      </ul>
    </section>
  );
}
