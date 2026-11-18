'use client';
import Link from 'next/link';
import { FileText, Loader2, Send } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, type Room } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { dateTime } from '@/lib/format';
import { isApiNotFound } from '@/components/claim';
import { PersonaCard, SimulationNotice } from '@/components/persona';
import { ConfidenceTracker } from '@/components/confidence';
import { QuoteUsage } from '@/components/quote-usage';
import { Turn, challengeText } from '@/components/room-turn';
import { Empty, ErrorState, Notice, Skeleton } from '@/components/ui';

const MAX_USER_TURNS = 12;

export function RoomView({ id }: { id: string }) {
  const [room, setRoom] = useState<Room>();
  const [loadError, setLoadError] = useState<ApiError>();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string>();
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await api.room(id);
      setRoom(next);
      setLoadError(undefined);
      return next;
    } catch (e) {
      setLoadError(e instanceof ApiError ? e : new ApiError(0, null));
      return undefined;
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const persona = useApi(room ? `persona:${room.persona_id}` : null, () => api.persona(room!.persona_id));
  const busy = sending || room?.status === 'generating';

  // The send request is one long call; read the room meanwhile so finished turns appear as they are saved.
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [busy, refresh]);

  // Follow new turns, but do not jump to the bottom when an existing room is first opened.
  const seen = useRef<number>(undefined);
  useEffect(() => {
    const n = room?.turns.length;
    if (n === undefined) return;
    if (seen.current !== undefined && n > seen.current) endRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    seen.current = n;
  }, [room?.turns.length]);

  const userTurns = room?.turns.filter((t) => t.kind === 'user').length ?? 0;
  const text = message.trim();
  const canSend = !busy && text.length >= 4 && text.length <= 1500 && userTurns < MAX_USER_TURNS;

  // Fills the follow-up into the input box; the user reads it and decides whether to send (each send costs model calls).
  function challenge(turn: Parameters<typeof challengeText>[0]) {
    setMessage(challengeText(turn));
    setSendError(undefined);
    inputRef.current?.focus();
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!canSend) return;
    setSending(true);
    setSendError(undefined);
    try {
      const next = await api.sendRoomMessage(id, text);
      setRoom(next);
      setMessage('');
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : '发送没有成功，请重试。');
      await refresh();
    } finally {
      setSending(false);
    }
  }

  if (loadError && !room) {
    if (isApiNotFound(loadError))
      return (
        <Empty title="找不到这个讨论室">
          <p>
            <Link href="/rooms" style={{ color: 'var(--accent)' }}>回到“作者分身讨论室”</Link>
          </p>
        </Empty>
      );
    return <ErrorState error={loadError} retry={refresh} />;
  }
  if (!room) return <Skeleton h={320} />;

  return (
    <>
      <nav className="crumbs" aria-label="位置" style={{ marginBottom: 16 }}>
        <Link href="/rooms">作者分身讨论室</Link>
        <span aria-hidden>/</span>
        <span aria-current="page">讨论室</span>
      </nav>
      <header className="page-head">
        <div>
          <div className="eyebrow" style={{ letterSpacing: 0 }}>{room.council ? '含 AI 辩论团' : '仅与作者分身讨论'}</div>
          <h1 className="page-title">{room.topic}</h1>
          <p className="lede">正在和“{room.author_label}”讨论。{userTurns} / {MAX_USER_TURNS} 次发言。</p>
        </div>
        <a className="btn" href={`/api/v1/rooms/${encodeURIComponent(room.id)}/report`} target="_blank" rel="noreferrer noopener">
          <FileText size={15} aria-hidden /> 查看讨论记录
        </a>
      </header>

      <div style={{ marginBottom: 18 }}>
        <SimulationNotice />
      </div>

      <div className="two-col">
        <section aria-label="对话" style={{ display: 'grid', gap: 14 }}>
          {room.turns.length === 0 && (
            <div className="card pad muted" style={{ fontSize: 14 }}>
              还没有发言。先说出你对“{room.topic}”的立场，分身会据此回应。
            </div>
          )}
          {room.turns.map((t, i) => (
            <Turn key={i} turn={t} persona={persona.data} onChallenge={challenge} challengeDisabled={busy || userTurns >= MAX_USER_TURNS} />
          ))}
          {busy && (
            <div className="card pad" role="status" aria-live="polite" style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 14 }}>
              <Loader2 size={16} className="spin" aria-hidden />
              正在生成回应，每轮通常需要几十秒。请不要重复提交。
            </div>
          )}
          {room.status === 'failed' && (
            <Notice tone="error" title="这一轮没有生成完成">
              {room.error ?? '模型调用失败。'} 已生成的部分已经保留，上面显示的就是已保存的内容。
            </Notice>
          )}
          <div ref={endRef} />

          <form className="card pad" onSubmit={send} aria-label="发言">
            <label className="field">
              <span>你的发言</span>
              <textarea
                className="textarea"
                aria-label="你的发言"
                ref={inputRef}
                style={{ minHeight: 96 }}
                placeholder="说出你的立场，或追问分身的某个说法。例如：我想把远程设为默认，你最担心什么？"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={1500}
                disabled={userTurns >= MAX_USER_TURNS}
              />
              <small>4–1500 字。分身最多参考最近 12 条发言。</small>
            </label>
            {userTurns >= MAX_USER_TURNS && (
              <div style={{ marginTop: 12 }}>
                <Notice tone="neutral">本场发言次数已用完，请回到入口新建讨论室。</Notice>
              </div>
            )}
            {sendError && (
              <div style={{ marginTop: 12 }}>
                <Notice tone="error">{sendError}</Notice>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 14 }}>
              <button className="btn primary" disabled={!canSend}>
                {sending ? <Loader2 size={16} className="spin" aria-hidden /> : <Send size={16} aria-hidden />}
                发送
              </button>
            </div>
          </form>
        </section>

        <aside aria-label="作者画像" style={{ display: 'grid', gap: 16 }}>
          <ConfidenceTracker roomId={room.id} userTurns={userTurns} avatarReplies={room.turns.filter((t) => t.kind === 'author_avatar').length} />
          <QuoteUsage persona={persona.data} turns={room.turns} />
          {persona.error ? <ErrorState error={persona.error} retry={persona.reload} /> : persona.data ? <PersonaCard persona={persona.data} /> : <Skeleton h={240} />}
          <p className="muted" style={{ fontSize: 12 }}>创建于 {dateTime(room.created_at)}</p>
        </aside>
      </div>
    </>
  );
}
