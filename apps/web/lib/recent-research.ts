// The API has no "list my investigations" endpoint, so this browser remembers the ids it created.
// Per-viewer convenience only; every status shown is still read back from the API.
const KEY = 'backcast:research-jobs';
const MAX = 8;

export type RecentResearch = { id: string; target: string; at: string };

export function readRecent(): RecentResearch[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(raw) ? raw.filter((r) => r && typeof r.id === 'string').slice(0, MAX) : [];
  } catch {
    return [];
  }
}

export function rememberResearch(item: RecentResearch) {
  try {
    const next = [item, ...readRecent().filter((r) => r.id !== item.id)].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: the job page still works by URL */
  }
}
