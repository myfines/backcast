'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, ApiError, type ResearchJob, type ResearchRequest, type TextAuditRequest } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { RESEARCH_STATUS, dateTime, today } from '@/lib/format';
import { readRecent, rememberResearch, type RecentResearch } from '@/lib/recent-research';
import { Notice, Tabs } from '@/components/ui';

type Mode = 'person' | 'excerpt';
type Kind = 'answer' | 'article';

export function ResearchForm() {
  const router = useRouter();
  const health = useApi('health', api.health);
  const [mode, setMode] = useState<Mode>('person');

  const [target, setTarget] = useState('');
  const [goal, setGoal] = useState('');
  const [domain, setDomain] = useState('');
  const [maxItems, setMaxItems] = useState(20);
  const [maxPages, setMaxPages] = useState(3);
  const [kinds, setKinds] = useState<Kind[]>(['answer', 'article']);
  const [analyst, setAnalyst] = useState<'worker' | 'openai'>('worker');

  const [sourceUrl, setSourceUrl] = useState('');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [published, setPublished] = useState('');
  const [edited, setEdited] = useState('');

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [recent, setRecent] = useState<RecentResearch[]>([]);
  useEffect(() => setRecent(readRecent()), []);

  const h = health.data;
  const toggleKind = (k: Kind) => setKinds((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
  const goalOk = goal.trim().length >= 3;
  const canSubmit =
    !busy && goalOk && (mode === 'person' ? target.trim().length > 0 && kinds.length > 0 : sourceUrl.trim().length > 0 && title.trim().length > 0 && text.trim().length >= 15);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(undefined);
    try {
      let job: ResearchJob;
      if (mode === 'person') {
        // `domain` has a server-side default, so leave it out when blank instead of inventing one.
        job = await api.research({ target: target.trim(), goal: goal.trim(), ...(domain.trim() ? { domain: domain.trim() } : {}), max_items: maxItems, max_pages: maxPages, kinds, analyst } as ResearchRequest);
      } else {
        job = await api.textAudit({ source_url: sourceUrl.trim(), title: title.trim(), text: text.trim(), goal: goal.trim(), ...(domain.trim() ? { domain: domain.trim() } : {}), published_at: published || null, edited_at: edited || null } as TextAuditRequest);
      }
      rememberResearch({ id: job.id, target: job.target, at: job.created_at });
      router.push(`/research/${encodeURIComponent(job.id)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '提交没有成功，请重试。');
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Investigate a Zhihu author</div>
          <h1 className="page-title">调查知乎答主</h1>
          <p className="lede">输入答主主页和你想判断的问题，系统会读取公开的回答与文章，提取其中可核查的事实，再逐条查证。结果只说明这批材料，不据此推荐或否定一个人。</p>
        </div>
      </header>

      <div className="two-col">
        <form className="card pad" onSubmit={submit} aria-label="调查表单">
          <Tabs
            label="调查方式"
            value={mode}
            onChange={(m) => {
              setMode(m);
              setError(undefined);
            }}
            items={[
              { value: 'person', label: '按答主采集历史' },
              { value: 'excerpt', label: '核查一段公开文字' },
            ]}
          />
          <div className="form-grid">
            {mode === 'person' ? (
              <label className="field full">
                <span>答主主页 *</span>
                <input className="input" aria-label="答主主页" placeholder="https://www.zhihu.com/people/答主标识" value={target} onChange={(e) => setTarget(e.target.value)} maxLength={500} />
                <small>只接受知乎个人主页链接或答主标识，不接受问题页或其他站点。</small>
              </label>
            ) : (
              <>
                <label className="field full">
                  <span>原文链接 *</span>
                  <input className="input" type="url" aria-label="原文链接" placeholder="https://zhuanlan.zhihu.com/p/……" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
                  <small>只接受知乎公开内容的链接。</small>
                </label>
                <label className="field">
                  <span>标题 *</span>
                  <input className="input" aria-label="标题" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
                </label>
                <label className="field">
                  <span>发表日期</span>
                  <input className="input" type="date" max={today()} value={published} onChange={(e) => setPublished(e.target.value)} />
                  <small>不确定就留空，系统不会替你补日期。</small>
                </label>
                <label className="field">
                  <span>最后编辑日期</span>
                  <input className="input" type="date" max={today()} value={edited} onChange={(e) => setEdited(e.target.value)} />
                  <small>页面只显示编辑时间时填这里，系统不会把它当作首次发表时间。</small>
                </label>
                <label className="field full">
                  <span>公开节选 *</span>
                  <textarea className="textarea" aria-label="公开节选" style={{ minHeight: 140 }} placeholder="粘贴你想核查的那几段原文" value={text} onChange={(e) => setText(e.target.value)} maxLength={40000} />
                  <small>已输入 {text.trim().length} 字 · 至少 15 字。节选不代表这位答主的历史。</small>
                </label>
              </>
            )}
            <label className="field full">
              <span>想判断什么 *</span>
              <input className="input" aria-label="想判断什么" placeholder="例如：检查他关于 AI 工具的技术说法有没有一手证据" value={goal} onChange={(e) => setGoal(e.target.value)} maxLength={1000} />
              <small>至少 3 个字。说得越具体，抽取出的事实越贴近你要判断的领域。</small>
            </label>
            <label className="field">
              <span>领域</span>
              <input className="input" placeholder="例如：编程技术（留空使用默认）" value={domain} onChange={(e) => setDomain(e.target.value)} maxLength={80} />
            </label>
            {mode === 'person' && (
              <>
                <label className="field">
                  <span>分析方式</span>
                  <select className="select" aria-label="分析方式" value={analyst} onChange={(e) => setAnalyst(e.target.value as 'worker' | 'openai')}>
                    <option value="worker">外部分析器回填</option>
                    <option value="openai">后端模型接口</option>
                  </select>
                  <small>
                    {analyst === 'worker'
                      ? '采集完成后停在“等待分析”，由持有工作器令牌的外部分析器回填。'
                      : h && !(h.ai && h.search)
                        ? '后端还没有配置模型或检索密钥，材料会保留并停在“等待分析”。'
                        : '采集后由后端调用模型和检索自动核查。'}
                  </small>
                </label>
                <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
                  <legend style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-2)', marginBottom: 6 }}>采集内容</legend>
                  <div className="chips">
                    <button type="button" className="chip" aria-pressed={kinds.includes('answer')} onClick={() => toggleKind('answer')}>
                      回答
                    </button>
                    <button type="button" className="chip" aria-pressed={kinds.includes('article')} onClick={() => toggleKind('article')}>
                      文章
                    </button>
                  </div>
                  {kinds.length === 0 && <small style={{ color: 'var(--wrong)' }}>至少选一种内容。</small>}
                </fieldset>
                <label className="field">
                  <span>最多读取条数</span>
                  <input className="input" type="number" min={1} max={40} value={maxItems} onChange={(e) => setMaxItems(Math.min(40, Math.max(1, Number(e.target.value) || 1)))} />
                  <small>1–40。达到预算时，结果会注明“不代表全量历史”。</small>
                </label>
                <label className="field">
                  <span>最多翻页数</span>
                  <input className="input" type="number" min={1} max={5} value={maxPages} onChange={(e) => setMaxPages(Math.min(5, Math.max(1, Number(e.target.value) || 1)))} />
                  <small>1–5。请求量被限制在这个范围内，避免触发平台限制。</small>
                </label>
              </>
            )}
          </div>
          {error && (
            <div style={{ marginTop: 14 }}>
              <Notice tone="error">{error}</Notice>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
            <button className="btn primary" disabled={!canSubmit}>
              {busy ? <Loader2 size={16} className="spin" aria-hidden /> : <Search size={16} aria-hidden />}
              开始调查
            </button>
          </div>
        </form>

        <aside aria-label="调查说明与最近记录" style={{ display: 'grid', gap: 16 }}>
          <div className="card pad">
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>调查会怎么进行</h2>
            <ol className="steps">
              <li>按预算读取答主公开的回答与文章，保存原文、链接、发表和编辑时间。</li>
              <li>从材料中提取可核查的事实，不把观点当作事实。</li>
              <li>为每条事实查找外部证据，并核对引用能否在原页面找到。</li>
              <li>汇总支持、不符和证据不足的数量。证据不足不算判错，也不据此推荐或否定这个人。</li>
            </ol>
            <p className="muted" style={{ fontSize: 13, marginTop: 14 }}>知乎可能要求登录或拒绝请求。遇到这种情况，任务会如实停在对应状态，不会当作“没有历史”。</p>
          </div>
          {recent.length > 0 && (
            <div className="card pad">
              <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>这台设备上的最近调查</h2>
              <ul className="list-plain">
                {recent.map((r) => (
                  <RecentRow key={r.id} item={r} />
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}

function RecentRow({ item }: { item: RecentResearch }) {
  const job = useApi(`research-recent:${item.id}`, () => api.researchJob(item.id));
  const s = job.data ? RESEARCH_STATUS[job.data.status] : undefined;
  return (
    <li style={{ justifyContent: 'space-between', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
      <span style={{ minWidth: 0 }}>
        <Link href={`/research/${encodeURIComponent(item.id)}`} style={{ overflowWrap: 'anywhere' }}>
          {job.data?.mode === 'provided_excerpt' ? job.data.goal : item.target}
        </Link>
        <br />
        <small className="muted">{dateTime(item.at)}</small>
      </span>
      <span className="tag outline">{job.error ? '无法读取' : (s?.label ?? '读取中……')}</span>
    </li>
  );
}
