'use client';
import Link from 'next/link';
import { KeyRound, Loader2, LogOut } from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { allAuthors, allClaims, api, ApiError, type Author, type Claim, type HumanResolution } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { SOURCE_TYPE, dateTime, day, today } from '@/lib/format';
import { AuditList, VerdictMark } from '@/components/claim';
import { ErrorState, Notice, Skeleton, Tabs } from '@/components/ui';

// The token lives only in this tab's sessionStorage. It is never bundled,
// never put in NEXT_PUBLIC_* vars, and is sent only as the X-Review-Token header.
const TOKEN_KEY = 'backcast.reviewToken';
function readToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? '';
  } catch {
    return '';
  }
}
function writeToken(v: string) {
  try {
    if (v) sessionStorage.setItem(TOKEN_KEY, v);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: keep in memory only */
  }
}

type Tab = 'queue' | 'resolve' | 'evidence' | 'sampling';

function explain(e: unknown) {
  if (e instanceof ApiError) {
    if (e.status === 503) return `${e.message}（后端 .env 未设置 REVIEW_API_TOKEN）`;
    if (e.status === 403) return `${e.message} 请检查令牌。`;
    return e.message;
  }
  return e instanceof Error ? e.message : '提交失败';
}

export function ReviewConsole() {
  const [token, setToken] = useState('');
  const [draft, setDraft] = useState('');
  const [tab, setTab] = useState<Tab>('queue');
  const [claimId, setClaimId] = useState('');
  const [version, setVersion] = useState(0);
  useEffect(() => setToken(readToken()), []);

  const data = useApi(`review:data:${version}`, async () => {
    const [authors, claims] = await Promise.all([allAuthors(), allClaims()]);
    return { authors, claims };
  });
  const authorName = useMemo(() => new Map((data.data?.authors ?? []).map((a) => [a.id, a.name])), [data.data]);
  const claim = data.data?.claims.find((c) => c.id === claimId);
  const bump = () => setVersion((v) => v + 1);

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Reviewer console</div>
          <h1 className="page-title">人工复核</h1>
          <p className="lede">处理纠错、裁定命题、标注证据出处、声明采样覆盖。每次提交都会写入审计记录，保留修改前后的内容。</p>
        </div>
      </header>

      <section className="card pad" aria-labelledby="token-h" style={{ marginBottom: 20 }}>
        <div className="panel-title">
          <h2 id="token-h" style={{ fontSize: 15, fontWeight: 600 }}>
            复核令牌
          </h2>
          <small>由后端 .env 的 REVIEW_API_TOKEN 配置</small>
        </div>
        {token ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span className="tag">
              <KeyRound size={13} aria-hidden /> 已在本标签页会话中保存令牌
            </span>
            <button
              className="btn small"
              onClick={() => {
                writeToken('');
                setToken('');
              }}
            >
              <LogOut size={14} aria-hidden /> 清除令牌
            </button>
          </div>
        ) : (
          <form
            style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}
            onSubmit={(e) => {
              e.preventDefault();
              writeToken(draft.trim());
              setToken(draft.trim());
              setDraft('');
            }}
          >
            <input className="input" style={{ flex: '1 1 240px' }} type="password" autoComplete="off" aria-label="复核令牌" placeholder="输入复核令牌" value={draft} onChange={(e) => setDraft(e.target.value)} />
            <button className="btn primary" disabled={!draft.trim()}>
              使用令牌
            </button>
          </form>
        )}
        <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
          令牌只保存在当前浏览器标签页，关闭即失效；令牌是否有效由后端在提交时校验（无效返回 403，未配置返回 503）。
        </p>
      </section>

      <Tabs
        label="复核任务"
        value={tab}
        onChange={setTab}
        items={[
          { value: 'queue', label: '纠错队列' },
          { value: 'resolve', label: '命题裁定' },
          { value: 'evidence', label: '证据出处' },
          { value: 'sampling', label: '采样声明' },
        ]}
      />

      {data.error ? (
        <ErrorState error={data.error} retry={data.reload} />
      ) : !data.data ? (
        <Skeleton h={240} />
      ) : tab === 'queue' ? (
        <Queue
          claims={data.data.claims}
          authorName={authorName}
          version={version}
          onPick={(id) => {
            setClaimId(id);
            setTab('resolve');
          }}
        />
      ) : tab === 'sampling' ? (
        <SamplingForm token={token} authors={data.data.authors} onDone={bump} />
      ) : (
        <div style={{ display: 'grid', gap: 18 }}>
          <ClaimPicker claims={data.data.claims} authorName={authorName} value={claimId} onChange={setClaimId} />
          {claim &&
            (tab === 'resolve' ? (
              <ResolutionForm key={claim.id} token={token} claim={claim} onDone={bump} />
            ) : (
              <EvidenceForm key={claim.id} token={token} claim={claim} onDone={bump} />
            ))}
          {claim && (
            <section className="card pad" aria-labelledby="audit-h">
              <h3 id="audit-h" style={{ fontSize: 15, fontWeight: 600 }}>
                该命题的审计历史
              </h3>
              <AuditList claimId={claim.id} version={version} />
            </section>
          )}
        </div>
      )}
    </>
  );
}

function Queue({ claims, authorName, version, onPick }: { claims: Claim[]; authorName: Map<string, string>; version: number; onPick: (id: string) => void }) {
  // Contract gap: there is no cross-claim review queue endpoint yet; assemble it from per-claim lists.
  const queue = useApi(`review:queue:${version}`, async () => {
    const rows = await Promise.all(claims.map(async (c) => ({ claim: c, reviews: await api.reviews(c.id) })));
    return rows.filter((r) => r.reviews.some((x) => x.status !== 'resolved'));
  });
  if (queue.error) return <ErrorState error={queue.error} retry={queue.reload} />;
  if (!queue.data) return <Skeleton h={120} />;
  if (!queue.data.length)
    return (
      <div className="empty">
        <h3>没有待处理的纠错</h3>
        <p>用户在“证据与判定”中提交的纠错会出现在这里。</p>
      </div>
    );
  return (
    <ul className="list-plain" style={{ gap: 12 }}>
      {queue.data.map(({ claim, reviews }) => (
        <li key={claim.id} className="card pad" style={{ display: 'block' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div className="dossier-no">
                {authorName.get(claim.author_id) ?? claim.author_id} · {claim.domain}
              </div>
              <strong className="serif" style={{ fontSize: 17 }}>
                {claim.title}
              </strong>
            </div>
            <VerdictMark status={claim.verdict.status} />
          </div>
          <ul className="review-list">
            {reviews
              .filter((r) => r.status !== 'resolved')
              .map((r) => (
                <li key={r.id}>
                  <time>{dateTime(r.created_at)}</time>
                  {r.note}
                </li>
              ))}
          </ul>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn small primary" onClick={() => onPick(claim.id)}>
              去裁定
            </button>
            <Link className="btn small" href={`/claims/${encodeURIComponent(claim.id)}`}>
              查看证据
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ClaimPicker({ claims, authorName, value, onChange }: { claims: Claim[]; authorName: Map<string, string>; value: string; onChange: (id: string) => void }) {
  const groups = useMemo(() => {
    const m = new Map<string, Claim[]>();
    for (const c of claims) m.set(c.author_id, [...(m.get(c.author_id) ?? []), c]);
    return [...m.entries()];
  }, [claims]);
  const current = claims.find((c) => c.id === value);
  return (
    <div className="card pad">
      <label className="field">
        <span>选择命题</span>
        <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {groups.map(([aid, list]) => (
            <optgroup key={aid} label={authorName.get(aid) ?? aid}>
              {list.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      {current && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
            <span className="dossier-no">
              发表 {day(current.published_at)} · 截止 {current.deadline ? day(current.deadline) : '未给出'}
            </span>
            <VerdictMark status={current.verdict.status} />
          </div>
          <p className="quote" style={{ marginTop: 8, paddingLeft: 12, borderLeft: '2px solid var(--line-2)', fontSize: 14 }}>
            {current.text}
          </p>
        </div>
      )}
    </div>
  );
}

function Submit({ busy, disabled, children }: { busy: boolean; disabled?: boolean; children: ReactNode }) {
  return (
    <button className="btn primary" disabled={busy || disabled}>
      {busy && <Loader2 size={15} className="spin" aria-hidden />}
      {children}
    </button>
  );
}

function useSubmit(onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [ok, setOk] = useState<string>();
  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError(undefined);
    setOk(undefined);
    try {
      setOk(await fn());
      onDone();
    } catch (e) {
      setError(explain(e));
    } finally {
      setBusy(false);
    }
  }
  const status = (
    <>
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">{ok}</Notice>}
    </>
  );
  return { busy, run, status };
}

function NeedToken({ token }: { token: string }) {
  return token ? null : <Notice tone="warn">请先在上方输入复核令牌。</Notice>;
}

function ResolutionForm({ token, claim, onDone }: { token: string; claim: Claim; onDone: () => void }) {
  const verified = claim.evidence.filter((e) => e.verified);
  const [status, setStatus] = useState<HumanResolution['status']>('insufficient');
  const [citations, setCitations] = useState<string[]>(claim.verdict.citations.filter((id) => verified.some((e) => e.id === id)));
  const [reason, setReason] = useState('');
  const [reviewer, setReviewer] = useState('');
  const [eventKey, setEventKey] = useState(claim.event_key ?? '');
  const [outcomeAt, setOutcomeAt] = useState(claim.outcome_at?.slice(0, 10) ?? '');
  const [original, setOriginal] = useState(false);
  const [snapUrl, setSnapUrl] = useState('');
  const [snapAt, setSnapAt] = useState('');
  const [format, setFormat] = useState<HumanResolution['forecast_format']>(claim.forecast_format);
  const [probability, setProbability] = useState(claim.probability != null ? String(Math.round(claim.probability * 100)) : '');
  const [quote, setQuote] = useState(claim.probability_quote ?? '');
  const [outcome, setOutcome] = useState<'' | '0' | '1'>('');
  const s = useSubmit(onDone);

  const probabilistic = format === 'probabilistic';
  const quoteInText = !quote || claim.text.includes(quote);
  const quotePercents = [...quote.matchAll(/(\d+(?:\.\d+)?)\s*[%％]/g)].map((m) => Number(m[1]));
  const quoteMatches = !probabilistic || !quote || !probability || quotePercents.includes(Number(probability));
  const valid =
    token &&
    citations.length > 0 &&
    reason.trim().length >= 15 &&
    reviewer.trim() &&
    eventKey.trim().length >= 3 &&
    outcomeAt &&
    (!original || (snapUrl && snapAt)) &&
    (!probabilistic || (probability && quote && outcome !== '' && quoteInText && quoteMatches));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    const body: HumanResolution = {
      status: probabilistic ? 'insufficient' : status,
      citations,
      reason: reason.trim(),
      reviewer: reviewer.trim(),
      event_key: eventKey.trim(),
      outcome_at: outcomeAt,
      original_version_confirmed: original,
      original_snapshot_url: original ? snapUrl.trim() : null,
      original_snapshot_at: original ? snapAt : null,
      forecast_format: format,
      probability: probabilistic ? Number(probability) / 100 : null,
      probability_quote: probabilistic ? quote : null,
      binary_outcome: probabilistic ? (Number(outcome) as 0 | 1) : null,
    };
    s.run(async () => {
      const updated = await api.resolve(token, claim.id, body);
      return `已裁定：${updated.verdict.reason}${updated.verdict.eligible ? '（计入严格成绩）' : '（不计入严格成绩）'}`;
    });
  }

  return (
    <form className="card pad" onSubmit={submit} aria-label="命题裁定">
      <div style={{ display: 'grid', gap: 16 }}>
        <NeedToken token={token} />
        <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
          <span>引用证据 *（只能引用已核对的证据）</span>
          {verified.length ? (
            verified.map((e) => (
              <label key={e.id} className="check">
                <input type="checkbox" checked={citations.includes(e.id)} onChange={(ev) => setCitations((c) => (ev.target.checked ? [...c, e.id] : c.filter((x) => x !== e.id)))} />
                <span>
                  <strong>{e.source}</strong> · {day(e.published_at)} · {SOURCE_TYPE[e.source_type]}
                  <br />
                  <small className="muted">{e.text.slice(0, 120)}</small>
                </span>
              </label>
            ))
          ) : (
            <Notice tone="warn">该命题没有已核对的证据，无法裁定。请先检索证据或补充证据。</Notice>
          )}
        </fieldset>
        <div className="form-grid">
          <label className="field">
            <span>预测形式</span>
            <select className="select" value={format} onChange={(e) => setFormat(e.target.value as HumanResolution['forecast_format'])}>
              <option value="categorical">明确命题</option>
              <option value="probabilistic">显式概率</option>
            </select>
          </label>
          {!probabilistic ? (
            <label className="field">
              <span>判定 *</span>
              <select className="select" value={status} onChange={(e) => setStatus(e.target.value as HumanResolution['status'])}>
                <option value="correct">结果吻合</option>
                <option value="wrong">结果落空</option>
                <option value="partial">部分吻合</option>
                <option value="insufficient">证据不足</option>
              </select>
            </label>
          ) : (
            <label className="field">
              <span>二元结果 *</span>
              <select className="select" value={outcome} onChange={(e) => setOutcome(e.target.value as '' | '0' | '1')}>
                <option value="">—</option>
                <option value="1">事件发生（1）</option>
                <option value="0">事件未发生（0）</option>
              </select>
            </label>
          )}
          {probabilistic && (
            <>
              <label className="field">
                <span>原文概率（%）*</span>
                <input className="input" type="number" min={0} max={100} step="0.1" value={probability} onChange={(e) => setProbability(e.target.value)} />
              </label>
              <label className="field">
                <span>概率摘录 *</span>
                <input className="input" value={quote} onChange={(e) => setQuote(e.target.value)} placeholder="从原文复制包含百分数的句子" />
                {!quoteInText && <small style={{ color: 'var(--wrong)' }}>摘录必须逐字出现在原文中</small>}
                {quoteInText && !quoteMatches && <small style={{ color: 'var(--wrong)' }}>摘录中的百分数与填写的概率不一致</small>}
              </label>
            </>
          )}
          <label className="field">
            <span>独立事件标识 *</span>
            <input className="input mono" value={eventKey} onChange={(e) => setEventKey(e.target.value)} placeholder="如 vision-pro-us-launch-2024" />
            <small>同一事件的多条记录用相同标识去重；对比时据此找共同事件</small>
          </label>
          <label className="field">
            <span>结果发生时间 *</span>
            <input className="input" type="date" max={today()} value={outcomeAt} onChange={(e) => setOutcomeAt(e.target.value)} />
          </label>
          <label className="field full">
            <span>裁定理由 *</span>
            <textarea className="textarea" style={{ minHeight: 90 }} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="说明口径与不确定性" />
            <small>{reason.trim().length} / 至少 15 字</small>
          </label>
          <label className="field">
            <span>复核人 *</span>
            <input className="input" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <label className="check full">
            <input type="checkbox" checked={original} onChange={(e) => setOriginal(e.target.checked)} />
            <span>已确认事前原始版本（需要快照链接，且快照时间早于事件与截止日）</span>
          </label>
          {original && (
            <>
              <label className="field">
                <span>原始快照链接 *</span>
                <input className="input" type="url" value={snapUrl} onChange={(e) => setSnapUrl(e.target.value)} placeholder="https://web.archive.org/…" />
              </label>
              <label className="field">
                <span>快照时间 *</span>
                <input className="input" type="date" value={snapAt} onChange={(e) => setSnapAt(e.target.value)} />
              </label>
            </>
          )}
        </div>
        {s.status}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Submit busy={s.busy} disabled={!valid}>
            提交裁定
          </Submit>
        </div>
      </div>
    </form>
  );
}

function EvidenceForm({ token, claim, onDone }: { token: string; claim: Claim; onDone: () => void }) {
  const [evId, setEvId] = useState(claim.evidence[0]?.id ?? '');
  const ev = claim.evidence.find((e) => e.id === evId);
  const [publishedAt, setPublishedAt] = useState(ev?.published_at?.slice(0, 10) ?? '');
  const [originUrl, setOriginUrl] = useState(ev?.origin_url ?? '');
  const [confirmed, setConfirmed] = useState(ev?.origin_confirmed ?? false);
  const [sourceType, setSourceType] = useState(ev?.source_type ?? 'unknown');
  const [reviewer, setReviewer] = useState('');
  const [reason, setReason] = useState('');
  const s = useSubmit(onDone);
  useEffect(() => {
    setPublishedAt(ev?.published_at?.slice(0, 10) ?? '');
    setOriginUrl(ev?.origin_url ?? '');
    setConfirmed(ev?.origin_confirmed ?? false);
    setSourceType(ev?.source_type ?? 'unknown');
  }, [ev]);

  if (!claim.evidence.length) return <Notice tone="neutral">该命题还没有证据。</Notice>;
  const valid = token && ev && reviewer.trim() && reason.trim().length >= 10 && (!confirmed || originUrl.trim());
  return (
    <form
      className="card pad"
      aria-label="证据出处标注"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid) return;
        s.run(async () => {
          await api.patchEvidence(token, evId, {
            published_at: publishedAt || null,
            origin_url: originUrl.trim() || null,
            origin_confirmed: confirmed,
            source_type: sourceType,
            reviewer: reviewer.trim(),
            reason: reason.trim(),
          });
          return '证据元数据已更新，审计记录保留修改前内容。';
        });
      }}
    >
      <div style={{ display: 'grid', gap: 16 }}>
        <NeedToken token={token} />
        <div className="form-grid">
          <label className="field full">
            <span>证据</span>
            <select className="select" value={evId} onChange={(e) => setEvId(e.target.value)}>
              {claim.evidence.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.source} · {e.id}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>证据发表日期</span>
            <input className="input" type="date" value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)} />
          </label>
          <label className="field">
            <span>来源类型</span>
            <select className="select" value={sourceType} onChange={(e) => setSourceType(e.target.value as typeof sourceType)}>
              <option value="primary">一手来源</option>
              <option value="secondary">二手转述</option>
              <option value="unknown">未确认</option>
            </select>
          </label>
          <label className="field full">
            <span>原始出处 URL</span>
            <input className="input" type="url" value={originUrl} onChange={(e) => setOriginUrl(e.target.value)} placeholder="https://" />
          </label>
          <label className="check full">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            <span>已确认与原始出处同源（需填写原始出处 URL）</span>
          </label>
          <label className="field">
            <span>复核人 *</span>
            <input className="input" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <label className="field">
            <span>理由 *</span>
            <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
            <small>{reason.trim().length} / 至少 10 字</small>
          </label>
        </div>
        {s.status}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Submit busy={s.busy} disabled={!valid}>
            保存标注
          </Submit>
        </div>
      </div>
    </form>
  );
}

function SamplingForm({ token, authors, onDone }: { token: string; authors: Author[]; onDone: () => void }) {
  const [authorId, setAuthorId] = useState('');
  const author = authors.find((a) => a.id === authorId);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [complete, setComplete] = useState(true);
  const [indexUrl, setIndexUrl] = useState('');
  const [reviewer, setReviewer] = useState('');
  const [note, setNote] = useState('');
  const s = useSubmit(onDone);
  const valid = token && author && start && end && start < end && indexUrl.trim() && reviewer.trim() && note.trim().length >= 15;
  return (
    <form
      className="card pad"
      aria-label="采样声明"
      onSubmit={(e) => {
        e.preventDefault();
        if (!valid || !author) return;
        s.run(async () => {
          await api.putSampling(token, author.id, {
            method: 'complete_window',
            domain: author.domain,
            start,
            end,
            complete,
            source_index_url: indexUrl.trim(),
            reviewer: reviewer.trim(),
            note: note.trim(),
          });
          return `已记录 ${author.name} 在 ${author.domain} 的采样声明。`;
        });
      }}
    >
      <div style={{ display: 'grid', gap: 16 }}>
        <NeedToken token={token} />
        <p className="muted" style={{ fontSize: 14 }}>
          声明已完整收录某段时间窗口内该作者在主领域的全部公开判断，用于排除“只挑成功案例”。
        </p>
        <div className="form-grid">
          <label className="field">
            <span>作者 *</span>
            <select className="select" value={authorId} onChange={(e) => setAuthorId(e.target.value)}>
              <option value="">—</option>
              {authors.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>领域（与档案主领域一致）</span>
            <input className="input" value={author?.domain ?? ''} readOnly />
          </label>
          <label className="field">
            <span>窗口开始 *</span>
            <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="field">
            <span>窗口结束 *</span>
            <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <label className="field full">
            <span>来源索引 URL *</span>
            <input className="input" type="url" value={indexUrl} onChange={(e) => setIndexUrl(e.target.value)} placeholder="作者文章列表或归档页" />
          </label>
          <label className="check full">
            <input type="checkbox" checked={complete} onChange={(e) => setComplete(e.target.checked)} />
            <span>窗口内判断已全部收录</span>
          </label>
          <label className="field">
            <span>复核人 *</span>
            <input className="input" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          </label>
          <label className="field">
            <span>说明 *</span>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
            <small>{note.trim().length} / 至少 15 字</small>
          </label>
        </div>
        {author?.sampling_protocol && (
          <Notice tone="info" title="已有采样声明">
            {author.sampling_protocol.start} — {author.sampling_protocol.end} · {author.sampling_protocol.reviewer}
          </Notice>
        )}
        {s.status}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Submit busy={s.busy} disabled={!valid}>
            保存采样声明
          </Submit>
        </div>
      </div>
    </form>
  );
}
