'use client';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import type { Persona, Room } from '@/lib/api';
import { dateTime } from '@/lib/format';
import { PersonaCard, SimulationNotice } from '@/components/persona';
import { QuoteUsage } from '@/components/quote-usage';
import { Turn } from '@/components/room-turn';
import { Notice } from '@/components/ui';
import recordedRoom from '@/lib/replay/discussion-room.json';
import recordedPersona from '@/lib/replay/author-persona.json';

// Both files are copies of docs/examples/*.json, saved from a real model run on 2026-11-17.
type Recording = Room & { model?: string; test_user?: string; test_result?: string };
const room = recordedRoom as unknown as Recording;
const persona = recordedPersona as unknown as Persona;

/** A recorded real discussion. It needs no backend and no credentials, and never calls a model. */
export function ReplayView() {
  const userTurns = room.turns.filter((t) => t.kind === 'user').length;
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow" style={{ letterSpacing: 0 }}>录制回放</div>
          <h1 className="page-title">{room.topic}</h1>
          <p className="lede">这是一次真实模型对话的录制：{userTurns} 次用户发言，作者分身和 AI 辩论团逐轮回应。回放不会调用模型，每条回应都可以展开所依据的原话。</p>
        </div>
        <Link className="btn primary" href="/rooms">
          自己试一试 <ArrowRight size={15} aria-hidden />
        </Link>
      </header>

      <div style={{ display: 'grid', gap: 12, marginBottom: 18 }}>
        <SimulationNotice />
        <Notice tone="info" title="关于这份录制">
          <ul className="list-plain" style={{ marginTop: 6 }}>
            <li>· 回应由 {room.model ?? '真实模型'} 生成，录制于 {dateTime(room.created_at)}。</li>
            {room.test_user && <li>· 用户发言：{room.test_user}</li>}
            {room.test_result && <li>· 结果：{room.test_result}</li>}
            <li>· 录制保留了分身说错和被追问后纠正的过程，没有修饰。</li>
          </ul>
        </Notice>
      </div>

      <div className="two-col">
        <section aria-label="对话回放" style={{ display: 'grid', gap: 14 }}>
          {room.turns.map((t, i) => (
            <Turn key={i} turn={t} persona={persona} />
          ))}
        </section>
        <aside aria-label="作者画像与原话使用" style={{ display: 'grid', gap: 16 }}>
          <QuoteUsage persona={persona} turns={room.turns} />
          <PersonaCard persona={persona} />
        </aside>
      </div>
    </>
  );
}
