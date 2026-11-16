import type { Metadata } from 'next';
import { ResearchJobView } from './research-job';

export const metadata: Metadata = { title: '调查进度' };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ResearchJobView id={id} />;
}
