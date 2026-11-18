import type { Metadata } from 'next';
import { RoomView } from './room-view';

export const metadata: Metadata = { title: '讨论室' };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RoomView id={id} />;
}
