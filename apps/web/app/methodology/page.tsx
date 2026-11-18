import type { Metadata } from 'next';
import { Methodology } from './methodology';

export const metadata: Metadata = { title: '评价方法' };

export default function Page() {
  return <Methodology />;
}
