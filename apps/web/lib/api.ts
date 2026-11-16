// Typed client for the backend /api/v1 contract (docs/openapi.json).
// Mirrors packages/api-client/client.ts and adds the endpoints the UI needs.
// No credentials are embedded: the review token is passed per call by the reviewer.
import type { components } from './contract/schema';

type S = components['schemas'];

/** Drops the `[key: string]: unknown` index signatures the generator adds, so Omit/props stay typed. */
type Known<T> = { [K in keyof T as string extends K ? never : number extends K ? never : K]: T[K] };

export type Scorecard = S['Scorecard'];
export type Evidence = Known<S['Evidence']> & { verification_method?: string; detected_date?: string | null };
export type Verdict = Known<S['Verdict']> & { reviewed_by?: string; reviewed_at?: string };
export type Claim = Omit<Known<S['Claim']>, 'evidence' | 'verdict'> & {
  evidence: Evidence[];
  verdict: Verdict;
  provenance?: string;
  probability_quote?: string | null;
  original_snapshot_url?: string | null;
  original_snapshot_at?: string | null;
};
export type Author = Known<S['AuthorSummary']> & {
  english?: string;
  initials?: string;
  color?: string;
  bio?: string;
  highlight?: string;
  takeaway?: string;
  started?: string;
  platform_url?: string | null;
  sampling_protocol?: S['SamplingProtocol'] | null;
};
export type Report = Omit<S['AuthorReport'], 'author' | 'claims'> & { author: Author; claims: Claim[] };
export type Comparison = S['Comparison'];
export type Job = S['Job'];
export type ImportResult = Omit<S['ImportResult'], 'claims'> & { claims: Claim[] };
export type CreateAuthor = S['CreateAuthor'];
export type ImportBody = Partial<S['ImportBody']>;
export type HumanResolution = S['HumanResolution'];
export type EvidenceMetadata = S['EvidenceMetadata'];
export type SamplingProtocol = S['SamplingProtocol'];
export type Page<T> = { items: T[]; total: number; offset: number; limit: number };
export type Health = { ok: boolean; ai: boolean; search: boolean; mode: string };
export type Methodology = {
  version: string;
  policy: Record<string, number>;
  metrics: string[];
  excluded: string[];
  references: string[];
  details: string;
};
export type ReviewNote = { id: string; claim_id: string; note: string; created_at: string; status?: string };
export type AuditRow = { id: number; action: string; record_id: string; created_at: string; data: Record<string, unknown> };
export type Source = { id: string; author_id: string; text: string; url?: string; published_at?: string | null; edited_at?: string | null; imported_at?: string; mode?: string };

type ValidationItem = { loc?: (string | number)[]; msg?: string };

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(describeDetail(status, detail));
  }
}

/** `detail` may be a string or a Pydantic validation array; make both readable. */
function describeDetail(status: number, detail: unknown): string {
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const lines = (detail as ValidationItem[]).map((d) => {
      const field = (d.loc || []).filter((x) => x !== 'body').join('.');
      return field ? `${field}：${d.msg ?? '无效'}` : d.msg ?? '输入无效';
    });
    if (lines.length) return lines.join('；');
  }
  return STATUS_TEXT[status] ?? `请求失败（${status}）`;
}

const STATUS_TEXT: Record<number, string> = {
  0: '无法连接后端服务，请确认 API 已在 8000 端口启动。',
  403: '复核令牌无效。',
  404: '记录不存在。',
  422: '输入未通过校验。',
  502: '外部服务失败，未产生新结论。',
  503: '服务未配置。',
};

type Params = Record<string, string | number | boolean | null | undefined>;
const enc = encodeURIComponent;

function query(params: Params = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  const s = p.toString();
  return s ? '?' + s : '';
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { cache: 'no-store', ...init });
  } catch {
    throw new ApiError(0, null);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body?.detail ?? null);
  return body as T;
}

function send<T>(method: string, path: string, body: unknown = {}, headers: Record<string, string> = {}) {
  return request<T>(path, { method, headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
}

const V1 = '/api/v1';
const reviewer = (token: string) => ({ 'X-Review-Token': token });

export const api = {
  health: () => request<Health>('/api/health'),
  methodology: () => request<Methodology>(`${V1}/methodology`),

  authors: (params: Params = {}) => request<Page<Author>>(`${V1}/authors${query(params)}`),
  author: (id: string) => request<Author>(`${V1}/authors/${enc(id)}`),
  createAuthor: (body: CreateAuthor) => send<Author>('POST', `${V1}/authors`, body),
  scorecard: (id: string, params: Params = {}) => request<Scorecard>(`${V1}/authors/${enc(id)}/scorecard${query(params)}`),
  report: (id: string, params: Params = {}) => request<Report>(`${V1}/authors/${enc(id)}/report${query(params)}`),

  claims: (params: Params = {}) => request<Page<Claim>>(`${V1}/claims${query(params)}`),
  claim: (id: string) => request<Claim>(`${V1}/claims/${enc(id)}`),
  audit: (id: string, params: Params = {}) => request<Page<AuditRow>>(`${V1}/claims/${enc(id)}/audit${query(params)}`),
  reviews: (id: string) => request<ReviewNote[]>(`${V1}/claims/${enc(id)}/reviews`),
  submitReview: (id: string, note: string) => send<{ id: string; status: string }>('POST', `${V1}/claims/${enc(id)}/reviews`, { note }),
  source: (id: string) => request<Source>(`${V1}/sources/${enc(id)}`),

  importContent: (body: ImportBody) => send<ImportResult>('POST', `${V1}/import`, body),
  compare: (body: S['CompareRequest']) => send<Comparison>('POST', `${V1}/compare`, body),

  verify: (id: string) => send<Job>('POST', `${V1}/claims/${enc(id)}/verification-jobs`),
  job: (id: string) => request<Job>(`${V1}/jobs/${enc(id)}`),

  toggleFollow: (id: string) => send<{ followed: boolean }>('POST', `${V1}/authors/${enc(id)}/follow`),

  /**
   * `follow` toggles server-side. To set a desired state safely (e.g. after a
   * network error) read the current value first and only toggle when needed.
   */
  async setFollow(id: string, desired: boolean): Promise<boolean> {
    const current = await request<Author>(`${V1}/authors/${enc(id)}`);
    if (current.followed === desired) return desired;
    const r = await send<{ followed: boolean }>('POST', `${V1}/authors/${enc(id)}/follow`);
    return r.followed;
  },

  // Manual review (requires backend REVIEW_API_TOKEN; never stored in code or NEXT_PUBLIC vars).
  resolve: (token: string, id: string, body: HumanResolution) =>
    send<Claim>('POST', `${V1}/claims/${enc(id)}/resolution`, body, reviewer(token)),
  patchEvidence: (token: string, id: string, body: EvidenceMetadata) =>
    send<Claim>('PATCH', `${V1}/evidence/${enc(id)}/metadata`, body, reviewer(token)),
  putSampling: (token: string, id: string, body: SamplingProtocol) =>
    send<Author>('PUT', `${V1}/authors/${enc(id)}/sampling`, body, reviewer(token)),
};

/** Fetch every page of authors (limit max 100). */
export async function allAuthors(params: Params = {}): Promise<Author[]> {
  const out: Author[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await api.authors({ ...params, limit: 100, offset });
    out.push(...page.items);
    if (out.length >= page.total || page.items.length === 0) return out;
  }
}

/** Fetch every claim matching the filter. */
export async function allClaims(params: Params = {}): Promise<Claim[]> {
  const out: Claim[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await api.claims({ ...params, limit: 100, offset });
    out.push(...page.items);
    if (out.length >= page.total || page.items.length === 0) return out;
  }
}
