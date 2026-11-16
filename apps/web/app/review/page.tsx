import type { Metadata } from 'next';
import { ReviewConsole } from './review-console';

export const metadata: Metadata = { title: '人工复核' };

export default function Page() {
  return <ReviewConsole />;
}
