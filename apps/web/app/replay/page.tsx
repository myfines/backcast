import type { Metadata } from 'next';
import { ReplayView } from './replay-view';

export const metadata: Metadata = { title: '真实讨论回放' };

export default function Page() {
  return <ReplayView />;
}
