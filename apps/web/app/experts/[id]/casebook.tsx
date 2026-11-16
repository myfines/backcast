'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ExternalLink, Link2, Scale, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { AUTHOR_TYPE, VERDICT, dateTime, day, today } from '@/lib/format';
import { FollowButton } from '@/components/expert';
import { ScorecardPanel } from '@/components/score';
import { ClaimDetail, ClaimDossier, ClaimTimeline, isApiNotFound } from '@/components/claim';
import { Avatar, Drawer, Empty, ErrorState, Notice, Skeleton, useToast } from '@/components/ui';

type Filter = 'all' | 'resolved' | 'open';

export function Casebook({ id, asOf, domain, claim }: { id: string; asOf: string; domain: string; claim: string }) {
  const router = useRouter();
  const [version, setVersion] = useState(0);
  const [filter, setFilter] = useState<Filter>('all');
  const [toast, showToast] = useToast();
  const report = useApi(`report:${id}:${asOf}:${domain}:${version}`, () => api.report(id, { as_of: asOf || undefined, domain: domain || undefined }));

  const href = useCallback(
    (next: Partial<{ asOf: string; domain: string; claim: string }>) => {
      const s = { asOf, domain, claim, ...next };
      const p = new URLSearchParams();
      if (s.asOf) p.set('as_of', s.asOf);
      if (s.domain) p.set('domain', s.domain);
      if (s.claim) p.set('claim', s.claim);
      const base = `/experts/${encodeURIComponent(id)}`;
      return p.size ? `${base}?${p}` : base;
    },
    [id, asOf, domain, claim],
  );
  const closeClaim = useCallback(() => router.replace(href({ claim: '' }), { scroll: false }), [router, href]);

  const r = report.data;
  useEffect(() => {
    if (r) document.title = `${r.author.name}的合订本 · Backcast 合订本`;
  }, [r]);

  const claims = useMemo(() => {
    const list = [...(r?.claims ?? [])].sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''));
    if (filter === 'resolved') return list.filter((c) => ['correct', 'wrong', 'partial'].includes(c.verdict.status));
    if (filter === 'open') return list.filter((c) => !['correct', 'wrong', 'partial'].includes(c.verdict.status));
    return list;
  }, [r, filter]);

  const domains = useMemo(() => [...new Set([r?.author.domain, ...(r?.claims ?? []).map((c) => c.domain), domain].filter(Boolean) as string[])], [r, domain]);

  if (report.error && !r) {
    if (isApiNotFound(report.error))
      return (
        <Empty title="档案不存在">
          <p>
            链接可能来自另一台机器的本地数据库。<Link href="/" style={{ color: 'var(--accent)' }}>返回发现页</Link>
          </p>
        </Empty>
      );
    return <ErrorState error={report.error} retry={report.reload} />;
  }
  if (!r)
    return (
      <div style={{ display: 'grid', gap: 16 }} aria-busy="true">
        <Skeleton h={160} />
        <Skeleton h={220} />
      </div>
    );

  const a = r.author;
  const unverifiedIdentity = a.type === '待确认';
  const selectedClaim = claim ? r.claims.find((c) => c.id === claim) : undefined;

  async function share() {
    const url = `${location.origin}/experts/${encodeURIComponent(id)}${asOf ? `?as_of=${asOf}` : ''}`;
    try {
      await navigator.clipboard.writeText(url);
      showToast('已复制分享链接；对方需要访问同一服务与数据库');
    } catch {
      showToast(url);
    }
  }

  return (
    <>
      <nav className="crumbs" aria-label="位置">
        <Link href="/">发现预测者</Link>
        <span aria-hidden>/</span>
        <Link href={`/?domain=${encodeURIComponent(a.domain)}`}>{a.domain}</Link>
        <span aria-hidden>/</span>
        <span aria-current="page">{a.name}</span>
      </nav>

      <header className="card cover" style={{ marginTop: 12 }}>
        <Avatar author={a} large />
        <div style={{ minWidth: 0 }}>
          <div className="tags" style={{ marginBottom: 8 }}>
            <span className="tag outline">{AUTHOR_TYPE[a.type] ?? a.type}</span>
            <span className="tag">{a.domain}</span>
            {a.tags.map((t) => (
              <span key={t} className="tag">
                {t}
              </span>
            ))}
          </div>
          <h1>
            {a.name}的合订本
            {a.english && a.english !== 'Imported contributor' && <span className="english">{a.english}</span>}
          </h1>
          <div className="expert-role" style={{ fontSize: 14 }}>
            {a.role}
          </div>
          {a.bio && <p className="bio">{a.bio}</p>}
          <div className="cover-meta">
            <span>收录始于 {a.started || '未知'}</span>
            <span>原始材料 {r.source_count} 份</span>
            <span>生成于 {dateTime(r.generated_at)}</span>
            {a.platform_url && (
              <a href={a.platform_url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
                公开主页 <ExternalLink size={12} aria-hidden style={{ display: 'inline' }} />
              </a>
            )}
          </div>
        </div>
        <div className="cover-actions">
          <FollowButton key={`${a.id}:${a.followed}`} author={a} />
          <Link className="btn small" href={`/compare?ids=${encodeURIComponent(a.id)}`}>
            <Scale size={14} aria-hidden /> 加入对比
          </Link>
          <button className="btn small" onClick={share}>
            <Link2 size={14} aria-hidden /> 分享
          </button>
        </div>
      </header>

      {(unverifiedIdentity || a.takeaway) && (
        <div style={{ marginTop: 14 }}>
          <Notice tone={unverifiedIdentity ? 'warn' : 'neutral'} title={unverifiedIdentity ? '作者身份与日期未经核实' : undefined}>
            {unverifiedIdentity ? '用户导入的档案仅供整理与复盘，不能直接用于公开排名。' : a.takeaway}
          </Notice>
        </div>
      )}

      <div className="card view-bar">
        <form
          style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}
          onSubmit={(e) => e.preventDefault()}
          aria-label="视图设置"
        >
          <label>
            截止日视图
            <input
              className="input"
              type="date"
              value={asOf}
              max={today()}
              onChange={(e) => router.replace(href({ asOf: e.target.value, claim: '' }), { scroll: false })}
            />
          </label>
          <label>
            领域
            <select className="select" value={domain} onChange={(e) => router.replace(href({ domain: e.target.value, claim: '' }), { scroll: false })}>
              <option value="">全部</option>
              {domains.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          {(asOf || domain) && (
            <button type="button" className="btn small quiet" onClick={() => router.replace(href({ asOf: '', domain: '', claim: '' }), { scroll: false })}>
              <X size={14} aria-hidden /> 清除
            </button>
          )}
        </form>
        {asOf ? <span className="asof-flag">截止 {day(asOf)} 的视图 · 不展示之后的结果与证据</span> : <span className="muted" style={{ fontSize: 13 }}>当前视图：截至今天</span>}
      </div>

      <section className="section" aria-labelledby="panel-h">
        <div className="section-head">
          <h2 className="section-title" id="panel-h">
            判断力面板
          </h2>
          <span className="muted mono">{r.scorecard.method_version}</span>
        </div>
        <ScorecardPanel card={r.scorecard} />
      </section>

      {r.claims.length > 0 && (
        <section className="section card pad" aria-labelledby="tl-h">
          <div className="panel-title">
            <h3 id="tl-h">判断时间轴</h3>
            <small>从发表到截止，再到结果</small>
          </div>
          <ClaimTimeline claims={r.claims} asOf={asOf || undefined} />
        </section>
      )}

      <section className="section" aria-labelledby="claims-h">
        <div className="section-head">
          <h2 className="section-title" id="claims-h">
            历史判断 <span className="muted tnum" style={{ fontSize: 15 }}>{r.claims.length}</span>
          </h2>
          <div className="chips" role="group" aria-label="按判定筛选">
            {(
              [
                ['all', '全部'],
                ['resolved', '已有结果'],
                ['open', '未到期 / 证据不足'],
              ] as [Filter, string][]
            ).map(([v, l]) => (
              <button key={v} className="chip" aria-pressed={filter === v} onClick={() => setFilter(v)}>
                {l}
              </button>
            ))}
          </div>
        </div>
        {claims.length ? (
          <div className="profile-timeline">
            {claims.map((c) => (
              <ClaimDossier key={c.id} claim={c} href={href({ claim: c.id })} />
            ))}
          </div>
        ) : (
          <Empty title={asOf ? '该截止日前没有已发表的判断' : '这里还没有判断'}>
            <p>
              <Link href={`/import?author=${encodeURIComponent(a.id)}`} style={{ color: 'var(--accent)' }}>
                为 {a.name} 追加一篇公开文章
              </Link>
            </p>
          </Empty>
        )}
        <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>
          判定标签：{Object.values(VERDICT).map((v) => v.label).join(' · ')}。“结果吻合”只说明这一条记录，不等于严格预测成绩。
          <Link href={`/import?author=${encodeURIComponent(a.id)}`} style={{ color: 'var(--accent)', marginLeft: 6 }}>
            追加文章 →
          </Link>
        </p>
      </section>

      <section className="section" aria-labelledby="lim-h">
        <h2 className="section-title" id="lim-h" style={{ fontSize: 17 }}>
          这份合订本不能说明什么
        </h2>
        <ul className="list-plain" style={{ marginTop: 10 }}>
          {r.scorecard.limitations.map((l) => (
            <li key={l} className="muted">
              — {l}
            </li>
          ))}
        </ul>
      </section>

      {claim && (
        <Drawer label="证据与判定" closeLabel="关闭证据" onClose={closeClaim}
          actions={<Link className="btn small quiet" href={`/claims/${encodeURIComponent(claim)}`}>整页打开</Link>}>
          <ClaimDetail claimId={claim} initial={selectedClaim} asOf={asOf || undefined} onChanged={() => setVersion((v) => v + 1)} />
        </Drawer>
      )}
      {toast}
    </>
  );
}
