'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, FilePlus2, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { allAuthors, api } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { ExpertCard } from '@/components/expert';
import { CardSkeleton, Empty, ErrorState, Notice } from '@/components/ui';

const PAGE = 12;

export function Discover({ domain, q, followed, page }: { domain: string; q: string; followed: boolean; page: number }) {
  const router = useRouter();
  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);

  const go = (next: Partial<{ domain: string; q: string; followed: boolean; page: number }>) => {
    const s = { domain, q, followed, page: 1, ...next };
    const p = new URLSearchParams();
    if (s.domain) p.set('domain', s.domain);
    if (s.q) p.set('q', s.q);
    if (s.followed) p.set('followed', '1');
    if (s.page > 1) p.set('page', String(s.page));
    router.replace(p.size ? `/?${p}` : '/', { scroll: false });
  };

  // Debounced search → URL (shareable state).
  useEffect(() => {
    if (text === q) return;
    const t = setTimeout(() => go({ q: text.trim() }), 280);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  const overview = useApi('overview', async () => {
    const [authors, claims] = await Promise.all([allAuthors(), api.claims({ limit: 1 })]);
    return {
      authors: authors.length,
      claims: claims.total,
      domains: [...new Set(authors.map((a) => a.domain))],
      eligible: authors.filter((a) => a.scorecard.readiness.eligible_for_ranking).length,
    };
  });

  const key = JSON.stringify({ domain, q, followed, page });
  const list = useApi(key, () =>
    api.authors({ domain: domain || undefined, q: q || undefined, followed: followed ? true : undefined, limit: PAGE, offset: (page - 1) * PAGE }),
  );
  const o = overview.data;
  const pages = list.data ? Math.max(1, Math.ceil(list.data.total / PAGE)) : 1;

  return (
    <>
      {!followed && (
        <section className="card hero" aria-labelledby="hero-title">
          <div>
            <div className="eyebrow">Follow judgment, not noise</div>
            <h1 id="hero-title" style={{ marginTop: 12 }}>
              专业，听他说；
              <br />
              <em>判断力，让时间说。</em>
            </h1>
            <p>从过去的判断与公开证据出发，找到值得持续关注的人。少看头衔与声量，多看有出处的历史记录。</p>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
              <Link className="btn primary" href="/import">
                <FilePlus2 size={16} aria-hidden /> 添加判断记录
              </Link>
              <Link className="btn" href="/methodology">
                我们如何评价 <ArrowRight size={15} aria-hidden />
              </Link>
            </div>
          </div>
          <div className="hero-ledger" aria-label="收录概况">
            <div className="ledger-row">
              <span>已收录预测者</span>
              <b className="tnum">{o ? o.authors : '—'}<small>位</small></b>
            </div>
            <div className="ledger-row">
              <span>已收录判断</span>
              <b className="tnum">{o ? o.claims : '—'}<small>条</small></b>
            </div>
            <div className="ledger-row">
              <span>覆盖领域</span>
              <b className="tnum">{o ? o.domains.length : '—'}<small>个</small></b>
            </div>
            <div className="ledger-row">
              <span>达到排名门槛</span>
              <b className="tnum">{o ? o.eligible : '—'}<small>位</small></b>
            </div>
          </div>
        </section>
      )}

      <section className={followed ? '' : 'section'} aria-labelledby="list-title">
        <div className="section-head">
          <div>
            <div className="eyebrow">{followed ? 'Following' : 'The people behind the predictions'}</div>
            <h2 className="page-title" id="list-title" style={{ fontSize: 26 }}>
              {followed ? '我的关注' : domain ? `${domain} · 预测者` : '从一个领域，认识一种判断力'}
            </h2>
          </div>
        </div>

        <div className="toolbar">
          <div className="chips" role="group" aria-label="按领域筛选">
            <button className="chip" aria-pressed={!domain} onClick={() => go({ domain: '' })}>
              全部领域
            </button>
            {(o?.domains ?? []).map((d) => (
              <button key={d} className="chip" aria-pressed={domain === d} onClick={() => go({ domain: d })}>
                {d}
              </button>
            ))}
          </div>
          <label className="search">
            <span className="sr-only">搜索预测者</span>
            <Search size={16} aria-hidden />
            <input className="input" type="search" placeholder="搜索姓名、身份或标签" value={text} onChange={(e) => setText(e.target.value)} />
          </label>
        </div>

        <p className="muted" style={{ fontSize: 13, marginBottom: 14 }} aria-live="polite">
          {list.data ? `找到 ${list.data.total} 位预测者` : '正在加载…'}
          {followed && ' · 关注仅保存在本机服务的数据库中'}
        </p>

        {list.error ? (
          <ErrorState error={list.error} retry={list.reload} />
        ) : !list.data ? (
          <CardSkeleton count={4} />
        ) : list.data.items.length === 0 ? (
          followed ? (
            <Empty title="还没有关注任何人">
              <p>在合订本页面点“关注记录”，之后可在这里找到。</p>
            </Empty>
          ) : (
            <Empty title="没有匹配的预测者">
              <p>换个关键词，或者<Link href="/import" style={{ color: 'var(--accent)' }}> 从一条公开判断建立档案</Link>。</p>
            </Empty>
          )
        ) : (
          <div className="grid-cards">
            {list.data.items.map((a) => (
              <ExpertCard key={`${a.id}:${a.followed}`} author={a} onFollowChange={followed ? list.reload : undefined} />
            ))}
          </div>
        )}

        {list.data && pages > 1 && (
          <nav className="pager" aria-label="分页">
            <button className="btn small" disabled={page <= 1} onClick={() => go({ page: page - 1 })}>
              上一页
            </button>
            <span className="tnum">
              {page} / {pages}
            </span>
            <button className="btn small" disabled={page >= pages} onClick={() => go({ page: page + 1 })}>
              下一页
            </button>
          </nav>
        )}
      </section>

      {!followed && (
        <div className="section">
          <Notice tone="neutral" title="样本小，结论也小">
            当前收录的是注明来源的人工转述案例，每位预测者仅少量记录，原始历史版本尚未独立存证，因此严格计分样本为 0——这是如实记录，不是系统故障。
          </Notice>
        </div>
      )}
    </>
  );
}
