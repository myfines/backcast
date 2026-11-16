import type { Metadata } from 'next';
import { Compare } from './compare';

export const metadata: Metadata = { title: '对比判断记录' };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? '';

export default async function Page({ searchParams }: { searchParams: Search }) {
  const s = await searchParams;
  const ids = one(s.ids).split(',').map((x) => x.trim()).filter(Boolean);
  return <Compare ids={[...new Set(ids)]} domain={one(s.domain)} />;
}
