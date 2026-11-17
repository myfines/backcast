// No "list rooms" endpoint exists, so this browser remembers the room ids it opened.
// Per-viewer convenience only; room content is always read back from the API.
const KEY = 'backcast:rooms';
const MAX = 8;

export type RecentRoom = { id: string; topic: string; label: string; at: string };

export function readRecentRooms(): RecentRoom[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(raw) ? raw.filter((r) => r && typeof r.id === 'string').slice(0, MAX) : [];
  } catch {
    return [];
  }
}

export function rememberRoom(item: RecentRoom) {
  try {
    localStorage.setItem(KEY, JSON.stringify([item, ...readRecentRooms().filter((r) => r.id !== item.id)].slice(0, MAX)));
  } catch {
    /* storage unavailable: rooms still open by URL */
  }
}
