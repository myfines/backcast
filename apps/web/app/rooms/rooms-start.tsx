'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2, MessagesSquare } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { dateTime } from '@/lib/format';
import { readRecentRooms, rememberRoom, type RecentRoom } from '@/lib/recent-rooms';
import { SimulationNotice } from '@/components/persona';
import { Notice } from '@/components/ui';

export function RoomsStart() {
  const router = useRouter();
  const [council, setCouncil] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [recent, setRecent] = useState<RecentRoom[]>([]);
  useEffect(() => setRecent(readRecentRooms()), []);

  async function start() {
    setBusy(true);
    setError(undefined);
    try {
      const room = await api.createDemoRoom(council);
      rememberRoom({ id: room.id, topic: room.topic, label: room.author_label, at: room.created_at ?? new Date().toISOString() });
      router.push(`/rooms/${encodeURIComponent(room.id)}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '没有创建成功，请重试。');
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Talk to an author&apos;s avatar</div>
          <h1 className="page-title">作者分身讨论室</h1>
          <p className="lede">说出你对一个具体问题的立场，和一位作者的 AI 分身连续讨论，需要时可以请 AI 辩论团加入。每条回应都会附上所依据的原话，方便你逐条核对。</p>
        </div>
      </header>

      <div style={{ marginBottom: 18 }}>
        <SimulationNotice />
      </div>

      <div className="two-col">
        <section className="card pad" aria-labelledby="start-h">
          <h2 id="start-h" style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>载入示例讨论室</h2>
          <p style={{ fontSize: 14 }}>
            示例分身“解虫”根据一篇真实知乎文章的选摘生成，议题是“远程办公是否应成为知识工作的默认模式”。进入后，在第一条发言里说出你的立场即可。
          </p>
          <label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 16, fontSize: 14 }}>
            <input type="checkbox" checked={council} onChange={(e) => setCouncil(e.target.checked)} style={{ marginTop: 4 }} />
            <span>
              邀请 AI 辩论团
              <br />
              <small className="muted">每次提问会多出两位虚构 AI 角色的回应，他们不代表任何真人。</small>
            </span>
          </label>
          {error && (
            <div style={{ marginTop: 14 }}>
              <Notice tone="error">{error}</Notice>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
            <button className="btn primary" onClick={start} disabled={busy}>
              {busy ? <Loader2 size={16} className="spin" aria-hidden /> : <MessagesSquare size={16} aria-hidden />}
              进入讨论室
            </button>
          </div>
        </section>

        <aside aria-label="使用说明与最近讨论" style={{ display: 'grid', gap: 16 }}>
          <div className="card pad">
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>请先了解</h2>
            <ul className="list-plain">
              <li>· 生成每轮回应需要几十秒，请耐心等待，不要重复提交。</li>
              <li>· 每场最多 12 次发言，用完后需要新建讨论室。</li>
              <li>· 分身只依据已收集的材料，材料有限，不代表完整的人。</li>
              <li>· 生成新回答需要后端配置了模型访问凭证，否则会提示失败。</li>
            </ul>
          </div>
          {recent.length > 0 && (
            <div className="card pad">
              <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>这台设备上的最近讨论</h2>
              <ul className="list-plain">
                {recent.map((r) => (
                  <li key={r.id} style={{ justifyContent: 'space-between', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                    <span style={{ minWidth: 0 }}>
                      <Link href={`/rooms/${encodeURIComponent(r.id)}`}>{r.topic}</Link>
                      <br />
                      <small className="muted">{r.label} · {dateTime(r.at)}</small>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
