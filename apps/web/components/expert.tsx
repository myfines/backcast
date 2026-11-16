'use client';
import Link from 'next/link';
import { ArrowRight, Bookmark, BookmarkCheck, Scale } from 'lucide-react';
import { useState } from 'react';
import { api, ApiError, type Author } from '@/lib/api';
import { AUTHOR_TYPE, pct } from '@/lib/format';
import { Avatar } from './ui';

/**
 * Follow is a server-side toggle. A plain click toggles once; if the request
 * fails ambiguously we read the current state before retrying, never POST twice blindly.
 */
export function FollowButton({ author, onChange, compact = false }: { author: Pick<Author, 'id' | 'name' | 'followed'>; onChange?: (followed: boolean) => void; compact?: boolean }) {
  const [followed, setFollowed] = useState(author.followed);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function toggle() {
    const desired = !followed;
    setBusy(true);
    setError(undefined);
    setFollowed(desired);
    try {
      let result: boolean;
      try {
        result = (await api.toggleFollow(author.id)).followed;
      } catch (e) {
        if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) result = await api.setFollow(author.id, desired);
        else throw e;
      }
      setFollowed(result);
      onChange?.(result);
      window.dispatchEvent(new Event('backcast:follow'));
    } catch (e) {
      setFollowed(!desired);
      setError(e instanceof Error ? e.message : '关注失败');
    } finally {
      setBusy(false);
    }
  }

  const label = followed ? '已关注' : '关注记录';
  return (
    <>
      <button
        className={'btn small' + (followed ? ' on' : '')}
        onClick={toggle}
        disabled={busy}
        aria-pressed={followed}
        aria-label={compact ? `${label}：${author.name}` : undefined}
        title={followed ? '取消关注' : '关注后可在“我的关注”中找到'}
      >
        {followed ? <BookmarkCheck size={15} aria-hidden /> : <Bookmark size={15} aria-hidden />}
        {!compact && label}
      </button>
      {error && (
        <span role="alert" style={{ fontSize: 12, color: 'var(--wrong)' }}>
          {error}
        </span>
      )}
    </>
  );
}

export function ExpertCard({ author }: { author: Author }) {
  const card = author.scorecard;
  const accuracy = card.categorical.accuracy;
  const href = `/experts/${encodeURIComponent(author.id)}`;
  return (
    <article className="card expert-card" aria-labelledby={`n-${author.id}`}>
      <div className="expert-top">
        <Avatar author={author} />
        <div className="who">
          <div className="tags" style={{ marginBottom: 6 }}>
            <span className="tag outline">{AUTHOR_TYPE[author.type] ?? author.type}</span>
            <span className="tag">{author.domain}</span>
          </div>
          <h3 className="expert-name" id={`n-${author.id}`}>
            <Link href={href}>{author.name}</Link>
          </h3>
          <div className="expert-role">{author.role}</div>
        </div>
        <FollowButton author={author} compact />
      </div>

      {author.highlight && <p className="expert-highlight">{author.highlight}</p>}

      <dl className="mini-metrics">
        <div>
          <dt>收录判断</dt>
          <dd className="tnum">{card.coverage.total_claims}</dd>
        </div>
        <div>
          <dt>严格计分样本</dt>
          <dd className="tnum">{card.coverage.scored_events}</dd>
        </div>
        <div>
          <dt>严格命中率</dt>
          <dd className={accuracy === null ? 'na' : 'tnum'}>{pct(accuracy)}</dd>
        </div>
      </dl>
      <div className="readiness-line">
        {card.readiness.eligible_for_ranking ? '样本达到比较门槛' : `样本不足，不排名 · 门槛 ${card.readiness.policy.minimum_events ?? 20} 个独立事件`}
      </div>

      <div className="card-foot">
        <Link className="open" href={href}>
          翻开合订本 <ArrowRight size={15} aria-hidden />
        </Link>
        <Link className="btn small quiet" href={`/compare?ids=${encodeURIComponent(author.id)}`}>
          <Scale size={14} aria-hidden /> 对比
        </Link>
      </div>
    </article>
  );
}
