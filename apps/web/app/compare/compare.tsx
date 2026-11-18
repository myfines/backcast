'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Check } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { allAuthors, api, type Author, type Comparison } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { AUTHOR_TYPE, NA, num, pct } from '@/lib/format';
import { Avatar, Empty, ErrorState, Notice, Skeleton } from '@/components/ui';

const MAX = 3; // CompareRequest.author_ids: 2–3

export function Compare({ ids, domain }: { ids: string[]; domain: string }) {
  const router = useRouter();
  const authors = useApi('compare:authors', () => allAuthors());
  const byId = useMemo(() => new Map((authors.data ?? []).map((a) => [a.id, a])), [authors.data]);
  // Local copy so rapid toggles compose instead of each reading the not-yet-updated URL.
  const [picked, setPicked] = useState(ids);
  const idsKey = ids.join(',');
  useEffect(() => setPicked(idsKey ? idsKey.split(',') : []), [idsKey]);
  const selected = picked.filter((id) => byId.size === 0 || byId.has(id));
  const ready = selected.length >= 2;
  const result = useApi(ready ? `compare:${selected.join(',')}:${domain}` : null, () => api.compare({ author_ids: selected, domain: domain || null }));

  const go = (nextIds: string[], nextDomain = domain) => {
    setPicked(nextIds);
    const p = new URLSearchParams();
    if (nextIds.length) p.set('ids', nextIds.join(','));
    if (nextDomain) p.set('domain', nextDomain);
    router.replace(p.size ? `/compare?${p}` : '/compare', { scroll: false });
  };
  const toggle = (id: string) => go(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id].slice(-MAX));

  const chosen = selected.map((id) => byId.get(id)).filter(Boolean) as Author[];
  const selectedDomains = [...new Set(chosen.map((a) => a.domain))];
  const allDomains = [...new Set((authors.data ?? []).map((a) => a.domain))];
  const crossDomain = selectedDomains.length > 1;

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Compare on the same questions</div>
          <h1 className="page-title">对比判断记录</h1>
          <p className="lede">并排查看两到三位预测者的记录。只有同一领域、共同事件足够多、各自样本也达标时，才比较高低；其余情况只并排展示，不宣布胜者。</p>
        </div>
      </header>

      <section className="card pad" aria-labelledby="pick-h">
        <div className="panel-title">
          <h2 id="pick-h" style={{ fontSize: 15, fontWeight: 600 }}>
            选择预测者 <span className="muted tnum">{selected.length} / {MAX}</span>
          </h2>
          {selected.length > 0 && (
            <button className="btn small quiet" onClick={() => go([], '')}>
              清空
            </button>
          )}
        </div>
        {authors.error ? (
          <ErrorState error={authors.error} retry={authors.reload} />
        ) : !authors.data ? (
          <Skeleton h={40} />
        ) : (
          <div className="compare-picker" role="group" aria-label="选择预测者">
            {authors.data.map((a) => {
              const on = selected.includes(a.id);
              return (
                <button key={a.id} className="pick" aria-pressed={on} aria-label={a.name} onClick={() => toggle(a.id)}>
                  <Avatar author={a} />
                  {a.name}
                  <small>{a.domain}</small>
                  {on && <Check size={14} aria-hidden />}
                </button>
              );
            })}
          </div>
        )}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginTop: 16 }}>
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <span>比较口径</span>
            <select className="select" style={{ width: 'auto' }} value={domain} onChange={(e) => go(selected, e.target.value)}>
              <option value="">不限领域（仅并排）</option>
              {allDomains.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          {!domain && selectedDomains.length === 1 && ready && (
            <button className="btn small" onClick={() => go(selected, selectedDomains[0])}>
              按“{selectedDomains[0]}”口径比较
            </button>
          )}
        </div>
      </section>

      {!ready ? (
        <div className="section">
          <Empty title="至少选择两位预测者">
            <p>先选同一领域的人更容易比较，例如消费科技领域的郭明錤和 Mark Gurman。</p>
          </Empty>
        </div>
      ) : result.error ? (
        <div className="section">
          <ErrorState error={result.error} retry={result.reload} />
        </div>
      ) : !result.data ? (
        <div className="section">
          <Skeleton h={260} />
        </div>
      ) : (
        <ComparisonView data={result.data} byId={byId} crossDomain={crossDomain} domains={selectedDomains} />
      )}
    </>
  );
}

function ComparisonView({ data, byId, crossDomain, domains }: { data: Comparison; byId: Map<string, Author>; crossDomain: boolean; domains: string[] }) {
  return (
    <section className="section" aria-labelledby="result-h">
      <h2 id="result-h" className="sr-only">
        对比结果
      </h2>
      <div className="comparison-notice" style={{ display: 'grid', gap: 10 }}>
        {crossDomain && (
          <Notice tone="warn" title="跨领域并排">
            所选预测者分属 {domains.join('、')}。不同领域的题目和难度不同，不能直接比较高低。
          </Notice>
        )}
        <Notice tone={data.comparable ? 'ok' : 'neutral'} title={data.comparable ? '满足比较政策' : '仅并排展示，不宣布胜者'}>
          {data.reason}
          {data.domain && ` 当前口径：${data.domain}。`}
        </Notice>
      </div>

      <div className="comparison-grid">
        {data.authors.map((row) => {
          const a = byId.get(row.author_id);
          const s = row.scorecard;
          const w = s.categorical.wilson_95;
          return (
            <article key={row.author_id} className="card" aria-label={a?.name ?? row.author_id}>
              <div className="expert-top">
                {a && <Avatar author={a} />}
                <div className="who">
                  <h3 className="expert-name">
                    <Link href={`/experts/${encodeURIComponent(row.author_id)}`}>{a?.name ?? row.author_id}</Link>
                  </h3>
                  <div className="expert-role">
                    {a ? `${AUTHOR_TYPE[a.type] ?? a.type} · ${a.domain}` : ''}
                  </div>
                </div>
              </div>
              <table className="compare-table">
                <tbody>
                  <tr>
                    <th scope="row">收录判断</th>
                    <td>{s.coverage.total_claims}</td>
                  </tr>
                  <tr>
                    <th scope="row">严格计分样本</th>
                    <td>{s.coverage.scored_events}</td>
                  </tr>
                  <tr>
                    <th scope="row">严格命中率</th>
                    <td>{pct(s.categorical.accuracy)}</td>
                  </tr>
                  <tr>
                    <th scope="row">95% Wilson 区间</th>
                    <td>{w ? `${pct(w[0])} – ${pct(w[1])}` : NA}</td>
                  </tr>
                  <tr>
                    <th scope="row">显式概率样本</th>
                    <td>{s.probabilistic.n}</td>
                  </tr>
                  <tr>
                    <th scope="row">Brier（全部）</th>
                    <td>{num(s.probabilistic.brier)}</td>
                  </tr>
                  <tr>
                    <th scope="row">共同事件</th>
                    <td>{row.paired_n}</td>
                  </tr>
                  <tr>
                    <th scope="row">共同事件 Brier</th>
                    <td>{row.paired_brier === null ? '无共同事件' : num(row.paired_brier)}</td>
                  </tr>
                </tbody>
              </table>
              <p className="readiness-line" style={{ marginTop: 12 }}>
                {s.readiness.eligible_for_ranking ? '样本达到比较门槛' : `样本不足：${s.readiness.warnings[0] ?? '未达门槛'}`}
              </p>
            </article>
          );
        })}
      </div>

      <div className="card pad" style={{ marginTop: 16 }}>
        <div className="panel-title">
          <h3>共同事件</h3>
          <small>各方都给出了显式概率、且结果记录一致的事件</small>
        </div>
        {data.event_keys.length ? (
          <div className="tags">
            {data.event_keys.map((k) => (
              <span key={k} className="tag mono">
                {k}
              </span>
            ))}
          </div>
        ) : (
          <p className="muted" style={{ fontSize: 14 }}>
            没有共同事件。同一口径下至少有 10 个共同的概率事件，才会计算并比较配对 Brier。
          </p>
        )}
        {data.conflicting_events.length > 0 && (
          <p style={{ marginTop: 10, fontSize: 13 }}>
            已排除结果或截止日记录不一致的事件：
            {data.conflicting_events.map((k) => (
              <span key={k} className="tag mono" style={{ marginLeft: 6 }}>
                {k}
              </span>
            ))}
          </p>
        )}
        <p className="muted mono" style={{ marginTop: 12 }}>
          {data.method_version}
        </p>
      </div>
    </section>
  );
}
