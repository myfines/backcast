'use client';
import Link from 'next/link';
import { ArrowRight, Loader2, Wand2 } from 'lucide-react';
import { useState } from 'react';
import { allAuthors, api, ApiError, type ImportResult } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { day, today } from '@/lib/format';
import { VerdictMark } from '@/components/claim';
import { Notice, Tabs } from '@/components/ui';

type Mode = 'new' | 'append';

export function ImportForm({ authorId }: { authorId: string }) {
  const [mode, setMode] = useState<Mode>(authorId ? 'append' : 'new');
  const health = useApi('health', api.health);
  const authors = useApi('import:authors', () => allAuthors());

  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [role, setRole] = useState('');
  const [platform, setPlatform] = useState('');
  const [target, setTarget] = useState(authorId);
  const [url, setUrl] = useState('');
  const [published, setPublished] = useState('');
  const [edited, setEdited] = useState('');
  const [text, setText] = useState('');

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [result, setResult] = useState<ImportResult & { createdName: string }>();

  const domains = [...new Set((authors.data ?? []).map((a) => a.domain))];
  const enoughSource = text.trim().length >= 15 || /^https?:\/\/\S+$/.test(url.trim());
  const canSubmit = enoughSource && (mode === 'new' ? name.trim().length > 0 : Boolean(target)) && !busy;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(undefined);
    setResult(undefined);
    let createdId: string | undefined;
    try {
      const common = { text: text.trim(), url: url.trim(), published_at: published || null, edited_at: edited || null };
      let r: ImportResult;
      let createdName = name.trim();
      if (mode === 'append') {
        r = await api.importContent({ ...common, author_id: target });
        createdName = authors.data?.find((a) => a.id === target)?.name ?? '';
      } else if (domain.trim() || role.trim() || platform.trim()) {
        // Profile details given: create the profile first, then attach the article to it.
        const author = await api.createAuthor({
          name: createdName,
          domain: domain.trim() || '其他',
          role: role.trim() || '用户提交 · 身份待核实',
          bio: '',
          platform_url: platform.trim() || null,
        });
        createdId = author.id;
        r = await api.importContent({ ...common, author_id: author.id });
      } else {
        r = await api.importContent({ ...common, author: createdName });
      }
      setResult({ ...r, createdName });
      setText('');
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : '导入没有成功，请重试';
      setError(createdId ? `${msg}档案已经建好，稍后可在合订本页追加文章。` : msg);
      if (createdId) setTarget(createdId);
    } finally {
      setBusy(false);
    }
  }

  const h = health.data;
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Add a public judgement</div>
          <h1 className="page-title">添加判断记录</h1>
          <p className="lede">粘贴一段带有明确时间的公开判断，系统会抽取候选判断并建档。没有证据时只显示“证据不足”或“尚未到期”，不会凭空下结论。</p>
        </div>
      </header>

      {h && (
        <div style={{ marginBottom: 18 }}>
          <Notice tone={h.ai ? 'ok' : 'neutral'} title={h.ai ? 'AI 抽取已启用' : 'AI 还没有配置，将用规则抽取候选判断'}>
            {h.ai ? '模型只在后端调用，密钥不会发到浏览器。' : '规则抽取不会生成事实判定；配置模型后，判断的拆分会更准确。'}
            {!h.search && ' 外部检索还没有配置，导入后不能自动检索证据。'}
          </Notice>
        </div>
      )}

      <div className="two-col">
        <form className="card pad" onSubmit={submit} aria-label="导入表单">
          <Tabs
            label="导入方式"
            value={mode}
            onChange={(m) => {
              setMode(m);
              setError(undefined);
            }}
            items={[
              { value: 'new', label: '新建档案' },
              { value: 'append', label: '追加到已有档案' },
            ]}
          />
          <div className="form-grid">
            {mode === 'new' ? (
              <>
                <label className="field">
                  <span>作者姓名 *</span>
                  <input className="input" placeholder="原文作者姓名" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
                </label>
                <label className="field">
                  <span>领域</span>
                  <input className="input" list="domain-list" placeholder="例如：新能源（留空则按内容推断）" value={domain} onChange={(e) => setDomain(e.target.value)} />
                  <datalist id="domain-list">
                    {domains.map((d) => (
                      <option key={d} value={d} />
                    ))}
                  </datalist>
                </label>
                <label className="field">
                  <span>身份说明</span>
                  <input className="input" placeholder="如：新能源行业分析师" value={role} onChange={(e) => setRole(e.target.value)} />
                </label>
                <label className="field">
                  <span>公开主页</span>
                  <input className="input" type="url" placeholder="https://" value={platform} onChange={(e) => setPlatform(e.target.value)} />
                </label>
              </>
            ) : (
              <label className="field full">
                <span>追加到 *</span>
                <select className="select" value={target} onChange={(e) => setTarget(e.target.value)} required>
                  <option value="">选择已有档案</option>
                  {(authors.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} · {a.domain}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="field full">
              <span>原文链接</span>
              <input className="input" type="url" placeholder="https://（只填链接时，会尝试读取公开正文）" value={url} onChange={(e) => setUrl(e.target.value)} />
            </label>
            <label className="field">
              <span>发表日期</span>
              <input className="input" type="date" max={today()} value={published} onChange={(e) => setPublished(e.target.value)} />
              <small>用来判断这条判断是不是“事前”作出的</small>
            </label>
            <label className="field">
              <span>最后编辑日期</span>
              <input className="input" type="date" max={today()} value={edited} onChange={(e) => setEdited(e.target.value)} />
              <small>事后编辑过的原文，不计入严格成绩</small>
            </label>
            <label className="field full">
              <span>原始正文</span>
              <textarea
                className="textarea"
                aria-label="原始正文"
                style={{ minHeight: 180 }}
                placeholder="粘贴原文。最好带有明确的时间点或截止日，例如“预计 2025 年底前……”"
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={40000}
              />
              <small>
                已输入 {text.trim().length} 字 · 至少 15 字，或提供能公开访问的链接
              </small>
            </label>
          </div>
          {error && (
            <div style={{ marginTop: 14 }}>
              <Notice tone="error">{error}</Notice>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
            <button className="btn primary" disabled={!canSubmit}>
              {busy ? <Loader2 size={16} className="spin" aria-hidden /> : <Wand2 size={16} aria-hidden />}
              提取判断，建立档案
            </button>
          </div>
        </form>

        <aside aria-label="导入结果与说明" style={{ display: 'grid', gap: 16 }}>
          {result ? (
            <div className="card pad" aria-live="polite">
              <div className="panel-title">
                <h2 style={{ fontSize: 16, fontWeight: 600 }}>已为 {result.createdName || '该作者'} 建立记录</h2>
                <span className="tag">{result.mode === 'ai' ? 'AI 抽取' : '规则抽取'}</span>
              </div>
              <p className="muted" style={{ fontSize: 14 }}>{result.message}</p>
              {result.claims.length ? (
                <ul className="list-plain" style={{ marginTop: 14 }}>
                  {result.claims.map((c) => (
                    <li key={c.id} style={{ justifyContent: 'space-between', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                      <span>
                        {c.title}
                        <br />
                        <small className="muted">截止 {c.deadline ? day(c.deadline) : '未给出'}</small>
                      </span>
                      <VerdictMark status={c.verdict.status} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ marginTop: 10, fontSize: 14 }}>没有抽取到可检验的判断。原文已经保存，可以再补充更具体的段落。</p>
              )}
              <Link className="btn primary" style={{ marginTop: 16, width: '100%' }} href={`/experts/${encodeURIComponent(result.author_id)}`}>
                打开合订本 <ArrowRight size={15} aria-hidden />
              </Link>
            </div>
          ) : (
            <div className="card pad">
              <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>导入之后会发生什么</h2>
              <ol className="steps">
                <li>保存原文、链接和日期，作为可追溯的原始材料。</li>
                <li>抽取带时间点的候选判断，观点和事实陈述分开标注。</li>
                <li>没到截止日的标为“尚未到期”；到期后可检索证据，或由人工复核裁定。</li>
                <li>作者身份和日期需要人工核实，核实之前不用于公开排名。</li>
              </ol>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
