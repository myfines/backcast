import type { Metadata } from 'next';
import { ResearchForm } from './research-form';

export const metadata: Metadata = { title: '调查知乎答主' };

export default function Page() {
  return <ResearchForm />;
}
