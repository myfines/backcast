'use client';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { ClaimDetail, isApiNotFound } from '@/components/claim';
import { Empty, ErrorState, Skeleton } from '@/components/ui';

export function ClaimPage({ id }: { id: string }) {
  const data = useApi(`claim-page:${id}`, async () => {
    const claim = await api.claim(id);
    const author = await api.author(claim.author_id).catch(() => undefined);
    return { claim, author };
  });
  if (data.error) {
    if (isApiNotFound(data.error))
      return (
        <Empty title="命题不存在">
          <p>
            <Link href="/" style={{ color: 'var(--accent)' }}>返回发现页</Link>
          </p>
        </Empty>
      );
    return <ErrorState error={data.error} retry={data.reload} />;
  }
  if (!data.data) return <Skeleton h={200} />;
  const { claim, author } = data.data;
  return (
    <div style={{ maxWidth: 820 }}>
      <nav className="crumbs" aria-label="位置" style={{ marginBottom: 16 }}>
        <Link href="/">发现预测者</Link>
        <span aria-hidden>/</span>
        {author ? <Link href={`/experts/${encodeURIComponent(author.id)}`}>{author.name}的合订本</Link> : <span>未知作者</span>}
        <span aria-hidden>/</span>
        <span aria-current="page">证据与判定</span>
      </nav>
      <ClaimDetail claimId={id} initial={claim} />
    </div>
  );
}
