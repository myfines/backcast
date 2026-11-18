import type { Metadata } from 'next';
import { RoomsStart } from './rooms-start';

export const metadata: Metadata = { title: '作者分身讨论室' };

export default function Page() {
  return <RoomsStart />;
}
