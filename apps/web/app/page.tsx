import { redirect } from 'next/navigation';
import { Discover } from './discover';

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? '';

export default async function Home({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  // Legacy share links from the first prototype: /?expert=kuo
  const expert = one(params.expert);
  if (expert) redirect(`/experts/${encodeURIComponent(expert)}`);
  return <Discover domain={one(params.domain)} q={one(params.q)} followed={one(params.followed) === '1'} page={Math.max(1, Number(one(params.page)) || 1)} />;
}
