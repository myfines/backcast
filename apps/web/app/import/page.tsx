import type { Metadata } from 'next';
import { ImportForm } from './import-form';

export const metadata: Metadata = { title: '添加判断记录' };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function Page({ searchParams }: { searchParams: Search }) {
  const s = await searchParams;
  const author = Array.isArray(s.author) ? s.author[0] : s.author;
  return <ImportForm authorId={author ?? ''} />;
}
