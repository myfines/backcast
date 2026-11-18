'use client';
import { HelpCircle } from 'lucide-react';
import type { Persona, RoomTurn } from '@/lib/api';
import { QuoteList } from './persona';

/** One line of a discussion. Avatar replies can offer a "challenge the source" action when the room is live. */
export function Turn({ turn, persona, onChallenge, challengeDisabled }: { turn: RoomTurn; persona?: Persona; onChallenge?: (turn: RoomTurn) => void; challengeDisabled?: boolean }) {
  const cls = turn.kind === 'user' ? 'user' : turn.kind === 'author_avatar' ? 'avatar-turn' : 'council';
  return (
    <article className={`turn ${cls}`} aria-label={turn.name}>
      <div className="turn-head">
        <b>{turn.name}</b>
        {turn.kind === 'fictional_council' && <span className="tag outline">虚构 AI 角色，不代表任何真人</span>}
        {turn.kind === 'author_avatar' && <span className="tag">AI 模拟</span>}
      </div>
      {turn.reply_to_quote && <p className="muted" style={{ fontSize: 12, marginBottom: 6 }}>回应你说的：“{turn.reply_to_quote}”</p>}
      <p style={{ fontSize: 14, whiteSpace: 'pre-wrap' }}>{turn.text}</p>
      {turn.quotes && turn.quotes.length > 0 && <QuoteList quotes={turn.quotes} persona={persona} />}
      {onChallenge && turn.kind === 'author_avatar' && (
        <div style={{ marginTop: 10 }}>
          <button type="button" className="btn small" onClick={() => onChallenge(turn)} disabled={challengeDisabled} title="把追问写进输入框，你确认后再发送">
            <HelpCircle size={14} aria-hidden /> 质疑出处
          </button>
        </div>
      )}
    </article>
  );
}

/** First sentence of a reply, shortened, used to point the follow-up at the exact claim. */
export function challengeText(turn: RoomTurn): string {
  const first = turn.text.split(/(?<=[。！？!?])/)[0]?.trim() ?? turn.text;
  const excerpt = first.length > 48 ? `${first.slice(0, 48)}……` : first;
  return `你刚才说“${excerpt}”。请指出这句话在你的原文里的依据；如果原文里没有，请直接承认。`;
}
