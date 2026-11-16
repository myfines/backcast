import { Casebook } from './casebook';

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? '';

export default async function ExpertPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const { id } = await params;
  const s = await searchParams;
  return <Casebook id={decodeURIComponent(id)} asOf={one(s.as_of)} domain={one(s.domain)} claim={one(s.claim)} />;
}
