'use client';
import Link from 'next/link';
import { ExternalLink, FileSearch, Loader2, Search, Send } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type Claim, type Evidence, type Job } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { AUDIT_ACTION, JOB_STATUS, KIND, CONDITION_STATE, LOGIC_STATUS, MODE_LABEL, OBSERVATION, SOURCE_TYPE, VERDICT, dateTime, verdictView, day, pct } from '@/lib/format';
import { ErrorState, Notice, Skeleton } from './ui';

export function VerdictMark({ status, kind }: { status: Claim['verdict']['status']; kind?: Claim['kind'] }) {
  const v = verdictView(status, kind);
  return (
    <span className={`stamp ${v.tone}`} title={v.hint}>
      {v.label}
    </span>
  );
}

/** How the analyst read the wording, kept apart from the verdict: reading, condition, logic. */
function InterpretationPanel({ claim }: { claim: Claim }) {
  const i = claim.interpretation!;
  const obs = claim.judgment_review?.observation;
  return (
    <section className="card pad" style={{ margin: '16px 0' }} aria-labelledby="interp-h">
      <div className="panel-title">
        <h3 id="interp-h" style={{ fontSize: 15, fontWeight: 600 }}>原意解读</h3>
        <span className="tag">{MODE_LABEL[i.mode] ?? i.mode}</span>
      </div>
      {i.reading && <p style={{ fontSize: 14 }}>{i.reading}</p>}
      {i.condition_quotes.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="muted" style={{ fontSize: 13 }}>
            作者设定的条件 · {CONDITION_STATE[i.condition_state] ?? i.condition_state}
          </div>
          <ul className="list-plain" style={{ marginTop: 6 }}>
            {i.condition_quotes.map((q) => (
              <li key={q}>“{q}”</li>
            ))}
          </ul>
          {i.condition_state !== 'met' && <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>条件没有确认发生，因此不按无条件预测判成败。</p>}
        </div>
      )}
      {i.mode === 'scenario' && <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>这是并列的可能情景，不是必然承诺，不判成败。</p>}
      {obs && <p style={{ fontSize: 14, marginTop: 12 }}>{OBSERVATION[obs] ?? obs}。这是单独的观察，不计入正式预测成绩。</p>}
      <div style={{ marginTop: 12 }}>
        <span className="tag outline">{LOGIC_STATUS[i.logic.status] ?? i.logic.status}</span>
        {i.logic.reason && <p style={{ fontSize: 13, marginTop: 8 }}>{i.logic.reason}</p>}
        {i.logic.quotes.length > 0 && (
          <ul className="list-plain" style={{ marginTop: 6 }}>
            {i.logic.quotes.map((q) => (
              <li key={q} className="muted">“{q}”</li>
            ))}
          </ul>
        )}
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>逻辑评价由模型依据作者原文给出，单列显示，不抵消事实错误；直觉和未决判断不因缺少推导扣分。</p>
      </div>
    </section>
  );
}

/** One claim as an archive page: date spine on the left, judgement on the right. */
export function ClaimDossier({ claim, href }: { claim: Claim; href: string }) {
  return (
    <article className="card dossier" aria-labelledby={`c-${claim.id}`}>
      <div className="dossier-spine">
        <div>
          发表<b>{day(claim.published_at)}</b>
        </div>
        <div>
          截止<b>{claim.deadline ? day(claim.deadline) : '未给出'}</b>
        </div>
        {claim.outcome_at && (
          <div>
            结果<b>{day(claim.outcome_at)}</b>
          </div>
        )}
      </div>
      <div className="dossier-body">
        <div className="dossier-head">
          <div style={{ minWidth: 0 }}>
            <div className="dossier-no">
              卷宗 No. {claim.id.slice(0, 12)} · {KIND[claim.kind]} · {claim.domain}
            </div>
            <h3 id={`c-${claim.id}`}>{claim.title}</h3>
          </div>
          <VerdictMark status={claim.verdict.status} kind={claim.kind} />
        </div>
        <p className="quote">{claim.text}</p>
        <div className="dossier-meta">
          <span>
            来源：
            {claim.source_url ? (
              <a href={claim.source_url} target="_blank" rel="noreferrer noopener">
                {claim.source_name}
              </a>
            ) : (
              claim.source_name
            )}
          </span>
          <span>证据 {claim.evidence.length} 条</span>
          {claim.forecast_format === 'probabilistic' && <span>显式概率 {pct(claim.probability ?? null)}</span>}
          {claim.provenance && <span>{claim.provenance}</span>}
        </div>
        <div className="dossier-foot">
          <span className="qualification">{claim.verdict.eligible ? '计入严格预测成绩' : claim.verdict.qualification || '不计入严格预测成绩'}</span>
          <Link className="btn small" href={href} scroll={false}>
            <FileSearch size={14} aria-hidden /> 查看证据与判定
          </Link>
        </div>
      </div>
    </article>
  );
}

const TONE_COLOR: Record<string, string> = { correct: '#2c6a44', wrong: '#973a2d', partial: '#85600f', pending: '#3b5876', muted: '#8b9086' };

/** Horizontal time strip: publication → deadline, outcome/evidence marked by verdict colour. */
export function ClaimTimeline({ claims, asOf }: { claims: Claim[]; asOf?: string }) {
  const rows = claims
    .map((c) => {
      const start = c.published_at ? Date.parse(c.published_at) : NaN;
      const end = c.deadline ? Date.parse(c.deadline) : NaN;
      const evDates = c.evidence.map((e) => (e.published_at ? Date.parse(e.published_at) : NaN)).filter((n) => !Number.isNaN(n));
      const outcome = c.outcome_at ? Date.parse(c.outcome_at) : evDates.length ? Math.min(...evDates) : NaN;
      return { c, start, end, outcome };
    })
    .filter((r) => !Number.isNaN(r.start))
    .sort((a, b) => a.start - b.start);
  if (!rows.length) return null;
  const cut = asOf ? Date.parse(asOf) : NaN;
  const all = rows.flatMap((r) => [r.start, r.end, r.outcome]).concat(Number.isNaN(cut) ? [] : [cut]).filter((n) => !Number.isNaN(n));
  let min = Math.min(...all);
  let max = Math.max(...all);
  const pad = Math.max((max - min) * 0.08, 1000 * 3600 * 24 * 20);
  min -= pad;
  max += pad;
  const W = 800;
  const L = 16;
  const R = 16;
  const rowH = 44;
  const top = 26;
  const H = top + rows.length * rowH + 10;
  const x = (t: number) => L + ((t - min) / (max - min)) * (W - L - R);
  const years: number[] = [];
  for (let y = new Date(min).getFullYear(); y <= new Date(max).getFullYear() + 1; y++) {
    const t = Date.UTC(y, 0, 1);
    if (t >= min && t <= max) years.push(t);
  }
  return (
    <figure style={{ margin: 0 }}>
      <div className="timeline-scroll" tabIndex={0} aria-label="判断时间轴（可横向滚动）">
      <svg className="timeline-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`判断时间轴，共 ${rows.length} 条`}>
        {years.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={14} y2={H - 4} stroke="#e4dece" />
            <text x={x(t) + 4} y={12} fontSize="11" fill="#8b9086" fontFamily="Consolas, monospace">
              {new Date(t).getUTCFullYear()}
            </text>
          </g>
        ))}
        {!Number.isNaN(cut) && (
          <g>
            <line x1={x(cut)} x2={x(cut)} y1={14} y2={H - 4} stroke="#3b5876" strokeDasharray="4 3" />
            <text x={x(cut) - 4} y={H - 8} fontSize="11" fill="#3b5876" textAnchor="end">
              截止日视图
            </text>
          </g>
        )}
        {rows.map((r, i) => {
          const y = top + i * rowH + 26;
          const tone = VERDICT[r.c.verdict.status]?.tone ?? 'muted';
          const color = TONE_COLOR[tone];
          const end = Number.isNaN(r.end) ? r.start : r.end;
          const labelX = Math.min(x(r.start), W - 260);
          return (
            <g key={r.c.id}>
              <text x={labelX} y={y - 10} fontSize="12.5" fill="#3a453e">
                {r.c.title.length > 30 ? r.c.title.slice(0, 30) + '…' : r.c.title}
              </text>
              <line x1={x(r.start)} x2={x(end)} y1={y} y2={y} stroke="#b9b19b" strokeWidth={3} strokeLinecap="round" strokeDasharray={r.c.verdict.status === 'pending' ? '5 4' : undefined} />
              <circle cx={x(r.start)} cy={y} r={5} fill="#fffdf8" stroke="#3a453e" strokeWidth={1.5} />
              {!Number.isNaN(r.end) && <line x1={x(r.end)} x2={x(r.end)} y1={y - 6} y2={y + 6} stroke="#3a453e" strokeWidth={1.5} />}
              {!Number.isNaN(r.outcome) && <rect x={x(r.outcome) - 5} y={y - 5} width={10} height={10} transform={`rotate(45 ${x(r.outcome)} ${y})`} fill={color} />}
            </g>
          );
        })}
      </svg>
      </div>
      <figcaption className="timeline-legend">
        <span>○ 发表</span>
        <span>| 截止日</span>
        <span>
          <i className="legend-swatch" style={{ background: TONE_COLOR.correct, transform: 'rotate(45deg)' }} />
          结果 / 最早证据（颜色＝判定）
        </span>
        <span>虚线＝尚未到期</span>
      </figcaption>
    </figure>
  );
}

function EvidenceItem({ e, cited }: { e: Evidence; cited: boolean }) {
  const webDate = e.verification_method?.includes('尚未核实');
  return (
    <li className={'evidence' + (cited ? ' cited' : '')} id={`ev-${e.id}`}>
      <div className="evidence-head">
        <a href={e.url} target="_blank" rel="noreferrer noopener">
          {e.source}
        </a>
        <span className="mono muted">{e.id.slice(0, 14)}</span>
      </div>
      <p>{e.text.length > 600 ? e.text.slice(0, 600) + '…' : e.text}</p>
      <div className="evidence-meta">
        <span className="tag">{e.published_at ? `证据日期 ${day(e.published_at)}${webDate ? '（网页提取，未独立确认）' : ''}` : '证据日期未知'}</span>
        <span className="tag">{SOURCE_TYPE[e.source_type] ?? e.source_type}</span>
        <span className="tag">{e.origin_confirmed ? '原始出处已确认' : '原始出处未确认'}</span>
        <span className="tag outline">检索于 {day(e.retrieved_at)}</span>
        {cited && <span className="tag" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>判定引用</span>}
      </div>
      {e.verification_method && (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          核对方式：{e.verification_method}
        </p>
      )}
      {e.origin_url && (
        <p style={{ fontSize: 12, marginTop: 4 }}>
          原始出处：
          <a href={e.origin_url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
            {e.origin_url}
          </a>
        </p>
      )}
    </li>
  );
}

const TERMINAL = new Set(['succeeded', 'failed']);

export function VerificationJobPanel({ claimId, onFinished }: { claimId: string; onFinished: () => void }) {
  const health = useApi('health', api.health);
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState<string>();
  const finished = useRef(onFinished);
  finished.current = onFinished;

  useEffect(() => {
    if (!job || TERMINAL.has(job.status)) return;
    let live = true;
    const t = setInterval(async () => {
      try {
        const next = await api.job(job.id);
        if (!live) return;
        setJob(next);
        if (TERMINAL.has(next.status)) finished.current();
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : '读取核验进度失败，请稍后刷新页面查看');
      }
    }, 1500);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [job]);

  async function start() {
    setError(undefined);
    try {
      const j = await api.verify(claimId);
      setJob(j);
      if (TERMINAL.has(j.status)) finished.current();
    } catch (e) {
      setError(e instanceof Error ? e.message : '核验任务没有启动，请重试');
    }
  }

  const ready = health.data?.ai;
  const running = job && !TERMINAL.has(job.status);
  return (
    <div>
      <button className="btn" onClick={start} disabled={!ready || !!running}>
        {running ? <Loader2 size={15} className="spin" aria-hidden /> : <Search size={15} aria-hidden />}
        检索外部证据并重新核验
      </button>
      {health.data && !ready && (
        <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
          后端还没有配置模型{health.data.search ? '' : '和检索服务'}，所以不能自动核验，也不会假装已经完成 AI 核验。配置方法见 README。
        </p>
      )}
      {health.data && ready && !health.data.search && (
        <p className="muted" style={{ fontSize: 13, marginTop: 8 }}>
          外部检索还没有配置，任务可能因为检索不到证据而失败；失败不会改变当前判定。
        </p>
      )}
      {job && (
        <div className="job" aria-live="polite">
          <strong>{JOB_STATUS[job.status] ?? job.status}</strong>
          <div className="job-steps" aria-hidden>
            {(['queued', 'running', job.status === 'failed' ? 'failed' : 'succeeded'] as const).map((s, i) => (
              <span key={s} className={job.status === s ? 'active' : ''}>
                {i > 0 && '→ '}
                {JOB_STATUS[s]}
              </span>
            ))}
          </div>
          {job.status === 'succeeded' && <p style={{ marginTop: 8 }}>任务结束不代表预测正确。请查看下方更新后的判定与引用，结果仍可能是“证据不足”或“尚未到期”。</p>}
          {job.status === 'failed' && <p style={{ marginTop: 8, color: 'var(--wrong)' }}>{job.error || '核验没有完成，也没有产生新结论；这条判断不会因此被判错。'}</p>}
        </div>
      )}
      {error && (
        <div style={{ marginTop: 10 }}>
          <Notice tone="error">{error}</Notice>
        </div>
      )}
    </div>
  );
}

function ReviewThread({ claimId, onSubmitted }: { claimId: string; onSubmitted: () => void }) {
  const reviews = useApi(`reviews:${claimId}`, () => api.reviews(claimId));
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const valid = note.trim().length >= 5;
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(undefined);
    try {
      await api.submitReview(claimId, note.trim());
      setNote('');
      reviews.reload();
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : '纠错没有提交成功，请重试');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <form onSubmit={submit} className="field" style={{ marginTop: 10 }}>
        <textarea
          className="textarea"
          style={{ minHeight: 90 }}
          aria-label="纠错说明"
          placeholder="例如：原文日期有误、证据出处应为一手来源、判定口径不清……（至少 5 个字）"
          value={note}
          maxLength={3000}
          onChange={(e) => setNote(e.target.value)}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <small>提交后进入人工复核队列。有待处理纠错时，这份档案会暂停排名资格。</small>
          <button className="btn" disabled={!valid || busy}>
            <Send size={14} aria-hidden /> 提交人工复核
          </button>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
      </form>
      {reviews.data && reviews.data.length > 0 && (
        <ul className="review-list">
          {reviews.data.map((r) => (
            <li key={r.id}>
              <time>
                {dateTime(r.created_at)} · {r.status === 'resolved' ? '已处理' : '待人工复核'}
              </time>
              {r.note}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AuditList({ claimId, version }: { claimId: string; version: number }) {
  const audit = useApi(`audit:${claimId}:${version}`, () => api.audit(claimId, { limit: 50 }));
  if (audit.error) return <ErrorState error={audit.error} retry={audit.reload} />;
  if (!audit.data) return <Skeleton h={40} />;
  if (!audit.data.items.length) return <p className="muted" style={{ fontSize: 13 }}>还没有变更记录。</p>;
  return (
    <ul className="audit-list">
      {audit.data.items.map((row) => (
        <li key={row.id}>
          <div>
            <time>{dateTime(row.created_at)}</time>
            {AUDIT_ACTION[row.action] ?? row.action}
          </div>
          <details>
            <summary>查看记录内容</summary>
            <pre>{JSON.stringify(row.data, null, 2)}</pre>
          </details>
        </li>
      ))}
    </ul>
  );
}

/** Full evidence & verdict view; used in the casebook drawer and the standalone claim page. */
export function ClaimDetail({ claimId, initial, onChanged, asOf }: { claimId: string; initial?: Claim; onChanged?: () => void; asOf?: string }) {
  const [version, setVersion] = useState(0);
  // In an as_of view the report already holds the time-limited claim; refetching would leak later evidence.
  const frozen = Boolean(asOf && initial && version === 0);
  const claim = useApi(frozen ? null : `claim:${claimId}:${version}`, () => api.claim(claimId));
  const c = claim.data ?? (version === 0 ? initial : undefined);
  if (claim.error && !c) return <ErrorState error={claim.error} retry={claim.reload} />;
  if (!c)
    return (
      <div style={{ display: 'grid', gap: 12 }} aria-busy="true">
        <Skeleton h={28} w="70%" />
        <Skeleton h={120} />
        <Skeleton h={80} />
      </div>
    );
  const cited = new Set(c.verdict.citations);
  const refresh = () => {
    setVersion((v) => v + 1);
    onChanged?.();
  };
  return (
    <article aria-labelledby="claim-title">
      {frozen && (
        <div style={{ marginBottom: 14 }}>
          <Notice tone="info" title={`截止 ${day(asOf)} 的视图`}>
            只显示当时已发表的证据，以及据此得出的判定。纠错和核验针对的是当前记录。
          </Notice>
        </div>
      )}
      <div className="eyebrow">
        卷宗 No. {c.id.slice(0, 12)} · {KIND[c.kind]} · {c.domain}
      </div>
      <h2 className="claim-title" id="claim-title">
        {c.title}
      </h2>

      <blockquote className="original" style={{ marginInline: 0 }}>
        {c.text}
        <footer style={{ marginTop: 10, fontSize: 13, color: 'var(--muted)' }}>
          {c.source_url ? (
            <a href={c.source_url} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
              {c.source_name} <ExternalLink size={12} aria-hidden style={{ display: 'inline' }} />
            </a>
          ) : (
            c.source_name
          )}
          {c.provenance && ` · ${c.provenance}`}
        </footer>
      </blockquote>

      <dl className="facts">
        <div>
          <dt>发表时间</dt>
          <dd>{day(c.published_at)}</dd>
        </div>
        <div>
          <dt>截止日</dt>
          <dd>{c.deadline ? day(c.deadline) : '原文未给出'}</dd>
        </div>
        <div>
          <dt>结果时间</dt>
          <dd>{c.outcome_at ? day(c.outcome_at) : '未裁定'}</dd>
        </div>
        <div>
          <dt>预测形式</dt>
          <dd>{c.forecast_format === 'probabilistic' ? `显式概率 ${pct(c.probability ?? null)}` : '明确命题'}</dd>
        </div>
        <div>
          <dt>原始版本</dt>
          <dd>{c.original_version_verified ? '已存证' : '未独立存证'}</dd>
        </div>
        {c.edited_at && (
          <div>
            <dt>最后编辑</dt>
            <dd>{day(c.edited_at)}</dd>
          </div>
        )}
      </dl>

      {c.interpretation && <InterpretationPanel claim={c} />}

      <section className="verdict-box" aria-labelledby="verdict-h">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <h3 id="verdict-h" style={{ fontSize: 15 }}>
            判定
          </h3>
          <VerdictMark status={c.verdict.status} kind={c.kind} />
        </div>
        <p className="reason">{c.verdict.reason}</p>
        {c.verdict.citations.length > 0 && (
          <p style={{ marginTop: 10, fontSize: 13, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="muted">引用：</span>
            {c.verdict.citations.map((id) => (
              <a key={id} className="cite" href={`#ev-${id}`}>
                {id.slice(0, 14)}
              </a>
            ))}
          </p>
        )}
        <p className="qualification" style={{ marginTop: 10 }}>
          {c.verdict.eligible ? '计入严格预测成绩。' : '不计入严格预测成绩。'}
          {c.verdict.qualification && ` ${c.verdict.qualification}`}
          {c.verdict.reviewed_by && ` · 人工裁定：${c.verdict.reviewed_by}`}
        </p>
      </section>

      <section className="section" aria-labelledby="ev-h" style={{ marginTop: 28 }}>
        <div className="section-head" style={{ marginBottom: 4 }}>
          <h3 id="ev-h" className="section-title" style={{ fontSize: 18 }}>
            证据 <span className="muted tnum" style={{ fontSize: 14 }}>{c.evidence.length}</span>
          </h3>
        </div>
        {c.evidence.length ? (
          <ul className="evidence-list" style={{ listStyle: 'none', padding: 0 }}>
            {c.evidence.map((e) => (
              <EvidenceItem key={e.id} e={e} cited={cited.has(e.id)} />
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ fontSize: 14, marginTop: 8 }}>
            还没有外部证据。没有证据时会一直显示“证据不足”，不会自动给出结论。
          </p>
        )}
        <div style={{ marginTop: 14 }}>
          <VerificationJobPanel claimId={c.id} onFinished={refresh} />
        </div>
      </section>

      <section className="section" aria-labelledby="rv-h" style={{ marginTop: 28 }}>
        <h3 id="rv-h" className="section-title" style={{ fontSize: 18 }}>
          纠错
        </h3>
        <p className="muted" style={{ fontSize: 13 }}>
          发现原文、日期、出处或判定口径有问题？写下说明，人工复核后会处理并留下记录。
        </p>
        <ReviewThread claimId={c.id} onSubmitted={refresh} />
      </section>

      <section className="section" aria-labelledby="au-h" style={{ marginTop: 28 }}>
        <h3 id="au-h" className="section-title" style={{ fontSize: 18 }}>
          审计历史
        </h3>
        <AuditList claimId={c.id} version={version} />
      </section>
    </article>
  );
}

export function isApiNotFound(e: unknown) {
  return e instanceof ApiError && e.status === 404;
}
