'use client';
import Link from 'next/link';
import { ArrowRight, ExternalLink, Loader2, RotateCw } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, type Claim, type ResearchJob } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { CAPTURE_METHOD, PROVENANCE, RESEARCH_STATUS, dateTime, day } from '@/lib/format';
import { isApiNotFound, VerdictMark } from '@/components/claim';
import { Empty, ErrorState, Notice, Skeleton } from '@/components/ui';

const MODE_LABEL: Record<string, string> = { person_history: '按答主采集历史', provided_excerpt: '核查一段公开文字' };

/** Poll while the backend is working; slower while it waits for an analyst; stop on a final state. */
function useResearchJob(id: string) {
  const [job, setJob] = useState<ResearchJob>();
  const [error, setError] = useState<ApiError>();
  const [epoch, setEpoch] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const load = useCallback(async () => {
    try {
      const next = await api.researchJob(id);
      setJob(next);
      setError(undefined);
      return next;
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, null));
      return undefined;
    }
  }, [id]);

  useEffect(() => {
    let live = true;
    const tick = async () => {
      const next = await load();
      if (!live) return;
      const s = next ? RESEARCH_STATUS[next.status] : undefined;
      if (next && s?.terminal) return;
      // A failed read keeps trying slowly; an active job is checked often, an awaiting one rarely.
      timer.current = setTimeout(tick, s?.active ? 2000 : 6000);
    };
    tick();
    return () => {
      live = false;
      clearTimeout(timer.current);
    };
  }, [load, epoch]);

  return { job, error, setJob, reload: load, restart: () => setEpoch((n) => n + 1) };
}

export function ResearchJobView({ id }: { id: string }) {
  const { job, error, setJob, reload, restart } = useResearchJob(id);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string>();

  if (error && !job) {
    if (isApiNotFound(error))
      return (
        <Empty title="找不到这个调查任务">
          <p>
            <Link href="/research" style={{ color: 'var(--accent)' }}>回到“调查知乎答主”</Link>
          </p>
        </Empty>
      );
    return <ErrorState error={error} retry={reload} />;
  }
  if (!job) return <Skeleton h={240} />;

  const s = RESEARCH_STATUS[job.status] ?? { label: job.status, tone: 'neutral' as const, active: false, terminal: false };
  const canRetry = job.mode === 'person_history' && ['needs_login', 'blocked', 'failed'].includes(job.status);

  async function retry() {
    setRetrying(true);
    setRetryError(undefined);
    try {
      setJob(await api.retryResearch(id));
      restart();
    } catch (e) {
      setRetryError(e instanceof ApiError ? e.message : '重试没有成功。');
    } finally {
      setRetrying(false);
    }
  }

  return (
    <>
      <nav className="crumbs" aria-label="位置" style={{ marginBottom: 16 }}>
        <Link href="/research">调查知乎答主</Link>
        <span aria-hidden>/</span>
        <span aria-current="page">调查进度</span>
      </nav>
      <header className="page-head">
        <div>
          <div className="eyebrow">{MODE_LABEL[job.mode] ?? job.mode}</div>
          <h1 className="page-title" style={{ overflowWrap: 'anywhere' }}>{job.mode === 'provided_excerpt' ? '公开文字核查' : job.target}</h1>
          <p className="lede">{job.goal}</p>
        </div>
        <span className="tag" role="status" aria-live="polite">
          {s.active && <Loader2 size={13} className="spin" aria-hidden />}
          {s.label}
        </span>
      </header>

      <div style={{ display: 'grid', gap: 16 }}>
        <StatusNotice job={job} />
        {error && <ErrorState error={error} retry={reload} />}
        {canRetry && (
          <div>
            <button className="btn" onClick={retry} disabled={retrying}>
              {retrying ? <Loader2 size={15} className="spin" aria-hidden /> : <RotateCw size={15} aria-hidden />} 重试采集
            </button>
            {retryError && (
              <div style={{ marginTop: 10 }}>
                <Notice tone="error">{retryError}</Notice>
              </div>
            )}
          </div>
        )}

        <div className="score-grid">
          <section className="card pad span-6" aria-labelledby="rc-cov">
            <div className="panel-title">
              <h2 id="rc-cov" style={{ fontSize: 15, fontWeight: 600 }}>实际采集范围</h2>
              <small>{job.coverage.complete ? '已读到列表末尾' : '不代表全量历史'}</small>
            </div>
            <Coverage job={job} />
          </section>
          <section className="card pad span-6" aria-labelledby="rc-doc">
            <div className="panel-title">
              <h2 id="rc-doc" style={{ fontSize: 15, fontWeight: 600 }}>已保存的原始材料</h2>
              <small>{job.documents.length} 份</small>
            </div>
            <Documents docs={job.documents} />
          </section>
        </div>

        {job.result && <Result job={job} result={job.result} />}
      </div>
    </>
  );
}

function StatusNotice({ job }: { job: ResearchJob }) {
  switch (job.status) {
    case 'queued':
    case 'collecting':
      return <Notice tone="info" title="正在读取公开材料">页面会自动刷新。读取受预算限制，中途被拒绝时会保留已取得的内容。</Notice>;
    case 'needs_login':
      return (
        <Notice tone="warn" title="知乎要求先登录">
          {job.error ?? '没有可用的登录态。'} 这不表示这位答主没有历史，也不是对人的评价。请先在本机完成知乎登录（步骤见 docs/ZHIHU_RESEARCH.md），再点“重试采集”。
        </Notice>
      );
    case 'blocked':
      return (
        <Notice tone="warn" title="知乎拒绝了请求">
          {job.error ?? '平台拒绝了请求。'} 系统已经停止，不会用重复请求或绕过限制的方式继续。这不表示这位答主没有历史。
        </Notice>
      );
    case 'awaiting_analysis':
      return (
        <Notice tone="info" title="材料已保存，正在等待分析">
          {job.mode === 'provided_excerpt'
            ? '这段节选需要由外部分析器回填核查结果。结果出来之前，页面不会显示任何结论。'
            : '采集已经结束。需要分析器回填核查结果，或后端配置好模型与检索服务后才会继续。结果出来之前，页面不会显示任何结论。'}
        </Notice>
      );
    case 'analyzing':
      return <Notice tone="info" title="正在查证">模型正在提取事实并查找外部证据，完成后会自动显示结果。</Notice>;
    case 'failed':
      return <Notice tone="error" title="调查没有完成">{job.error ?? '任务失败。'} 没有生成任何结论；已保存的材料仍然保留。</Notice>;
    case 'succeeded':
      return job.result ? null : <Notice tone="neutral">任务已结束，但后端没有返回结果。</Notice>;
    default:
      return null;
  }
}

function Coverage({ job }: { job: ResearchJob }) {
  const c = job.coverage;
  const ends = Object.entries(c.reached_end ?? {});
  const KIND_LABEL: Record<string, string> = { answer: '回答', article: '文章' };
  return (
    <>
      <dl className="kv" style={{ marginTop: 0 }}>
        <dt>取得正文</dt>
        <dd>{c.captured ?? 0} 份</dd>
        {c.requests !== undefined && (
          <>
            <dt>请求次数</dt>
            <dd>{c.requests}</dd>
          </>
        )}
        {(c.first_published_at || c.last_published_at) && (
          <>
            <dt>发表时间跨度</dt>
            <dd>
              {day(c.first_published_at)} – {day(c.last_published_at)}
            </dd>
          </>
        )}
        {ends.map(([kind, reached]) => (
          <KvRow key={kind} label={`${KIND_LABEL[kind] ?? kind}列表`} value={reached ? '已读到末尾' : '未读到末尾'} />
        ))}
        <dt>创建时间</dt>
        <dd>{dateTime(job.created_at)}</dd>
      </dl>
      {(c.warnings?.length ?? 0) > 0 && (
        <ul className="list-plain" style={{ marginTop: 14 }}>
          {c.warnings!.map((w) => (
            <li key={w} className="muted">
              · {w}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function KvRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function Documents({ docs }: { docs: ResearchJob['documents'] }) {
  if (!docs.length) return <p className="muted" style={{ fontSize: 14 }}>还没有取得任何正文。</p>;
  return (
    <ul className="list-plain">
      {docs.map((d) => (
        <li key={d.id ?? d.url} style={{ borderTop: '1px solid var(--line)', paddingTop: 10, display: 'block' }}>
          <a href={d.url} target="_blank" rel="noreferrer noopener" style={{ overflowWrap: 'anywhere' }}>
            {d.title} <ExternalLink size={12} aria-hidden />
          </a>
          <br />
          <small className="muted">
            {d.published_at ? `发表 ${day(d.published_at)}` : '发表时间未确认'}
            {d.edited_at ? ` · 编辑 ${day(d.edited_at)}` : ''}
            {d.capture_method ? ` · ${CAPTURE_METHOD[d.capture_method] ?? d.capture_method}` : ''}
            {d.text_truncated ? ' · 正文过长，已截断' : ''}
          </small>
        </li>
      ))}
    </ul>
  );
}

function Result({ job, result }: { job: ResearchJob; result: NonNullable<ResearchJob['result']> }) {
  const f = result.facts;
  const stats: { label: string; value: number }[] = [
    { label: '有证据支持', value: f.supported },
    { label: '证据与之不符', value: f.contradicted },
    { label: '部分支持', value: f.partial },
    { label: '证据不足', value: f.insufficient },
    { label: '无法验证', value: f.unverifiable },
  ];
  return (
    <section className="card pad" aria-labelledby="rc-res">
      <div className="panel-title">
        <h2 id="rc-res" style={{ fontSize: 16, fontWeight: 600 }}>核查结果</h2>
        <small>
          {result.model ? `${result.model} · ` : ''}
          {result.assessment_time ? dateTime(result.assessment_time) : ''}
        </small>
      </div>
      <p style={{ fontSize: 15 }}>{result.summary}</p>
      <div className="stat-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12, margin: '16px 0' }}>
        {stats.map((st) => (
          <div key={st.label} style={{ borderTop: '1px solid var(--line)', paddingTop: 8 }}>
            <div className="big-num" style={{ fontSize: 28 }}>{st.value}</div>
            <small className="muted">{st.label}（条）</small>
          </div>
        ))}
      </div>
      {!result.can_recommend_person && (
        <Notice tone="neutral" title="不据此推荐或否定这个人">
          这是对已取得材料中 {f.total} 条事实的核查。样本范围有限，预测资格、版本存证与长期表现仍然分别评价。
        </Notice>
      )}
      {result.analyst_summary && (
        <p className="muted" style={{ fontSize: 14, marginTop: 14 }}>
          分析器说明：{result.analyst_summary}
          {result.model_provenance && <> （{PROVENANCE[result.model_provenance] ?? result.model_provenance}）</>}
        </p>
      )}
      {result.limitations.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '16px 0 8px' }}>限制</h3>
          <ul className="list-plain">
            {result.limitations.map((l) => (
              <li key={l} className="muted">
                · {l}
              </li>
            ))}
          </ul>
        </>
      )}
      {(result.rejected_evidence?.length ?? 0) > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '16px 0 8px' }}>没有被采纳的证据</h3>
          <ul className="list-plain">
            {result.rejected_evidence!.map((r) => (
              <li key={r.url} className="muted" style={{ overflowWrap: 'anywhere' }}>
                · {r.url}：{rejectReason(r.reason)}
              </li>
            ))}
          </ul>
        </>
      )}
      <h3 style={{ fontSize: 14, fontWeight: 600, margin: '16px 0 8px' }}>逐条查看</h3>
      <ClaimList ids={result.claim_ids} />
      {job.author_id && (
        <Link className="btn primary" style={{ marginTop: 16 }} href={`/experts/${encodeURIComponent(job.author_id)}`}>
          打开合订本 <ArrowRight size={15} aria-hidden />
        </Link>
      )}
    </section>
  );
}

function rejectReason(code: string) {
  return code === 'fetch_or_quote_validation_failed' ? '页面没有取回，或原文摘录没有在页面里找到' : code;
}

function ClaimList({ ids }: { ids: string[] }) {
  const claims = useApi(ids.length ? `research-claims:${ids.join(',')}` : null, () => Promise.all(ids.map((cid) => api.claim(cid))));
  if (!ids.length) return <p className="muted" style={{ fontSize: 14 }}>没有提取出可核查的事实。</p>;
  if (claims.error) return <ErrorState error={claims.error} retry={claims.reload} />;
  if (!claims.data) return <Skeleton h={80} />;
  return (
    <ul className="list-plain">
      {claims.data.map((c: Claim) => (
        <li key={c.id} style={{ justifyContent: 'space-between', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
          <Link href={`/claims/${encodeURIComponent(c.id)}`} style={{ minWidth: 0 }}>
            {c.title}
          </Link>
          <VerdictMark status={c.verdict.status} />
        </li>
      ))}
    </ul>
  );
}
