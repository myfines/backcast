import type { components } from './schema';

export type Author = components['schemas']['AuthorSummary'];
export type Claim = components['schemas']['Claim'];
export type Scorecard = components['schemas']['Scorecard'];
export type Report = components['schemas']['AuthorReport'];
export type Job = components['schemas']['Job'];
export type Comparison = components['schemas']['Comparison'];
export type ResearchJob = components['schemas']['ResearchJob'];
export type Page<T> = {items:T[];total:number;offset:number;limit:number};
type Params = Record<string,string|number|boolean|undefined>;

export type SourceQuote = {source_id:string;quote:string};
export type PersonaFacet = {kind:'view'|'value'|'principle'|'style';description:string;quotes:SourceQuote[]};
export type AuthorPersona = {id:string;author_name:string;label:string;facets:PersonaFacet[];unknowns:string[];documents:{id:string;url:string;text:string;title?:string}[]};
export type PersonaReply = {persona_id:string;label:string;text:string;quotes:SourceQuote[];reply_to_quote?:string};
export type RoomTurn = {role:'user'|'assistant';kind:'user'|'author_avatar'|'fictional_council';name:string;text:string;quotes?:SourceQuote[];reply_to_quote?:string};
export type DiscussionRoom = {id:string;persona_id:string;topic:string;council:boolean;author_label:string;status:'ready'|'generating'|'failed';turns:RoomTurn[];error?:string};

export class ApiError extends Error {
  constructor(public status:number, public detail:unknown) {
    super(typeof detail === 'string' ? detail : `API request failed (${status})`);
  }
}

/** Runtime-free typed fetch client. No credentials are embedded. */
export function createBackcastClient(baseUrl='/api/v1') {
  async function request<T>(path:string,init?:RequestInit):Promise<T> {
    const response=await fetch(baseUrl.replace(/\/$/,'')+path,init);
    const body=await response.json().catch(()=>null);
    if(!response.ok) throw new ApiError(response.status,body?.detail??response.statusText);
    return body as T;
  }
  const encode=encodeURIComponent;
  const query=(params:Params={})=>{const p=new URLSearchParams();for(const [key,value] of Object.entries(params))if(value!==undefined)p.set(key,String(value));return p.size?'?'+p.toString():'';};
  const post=<T>(path:string,body:unknown={})=>request<T>(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  return {
    authors:(params:Params={})=>request<Page<Author>>('/authors'+query(params)),
    author:(id:string)=>request<Author>('/authors/'+encode(id)),
    createAuthor:(body:components['schemas']['CreateAuthor'])=>post<Author>('/authors',body),
    scorecard:(id:string,params:Params={})=>request<Scorecard>('/authors/'+encode(id)+'/scorecard'+query(params)),
    report:(id:string,params:Params={})=>request<Report>('/authors/'+encode(id)+'/report'+query(params)),
    claims:(params:Params={})=>request<Page<Claim>>('/claims'+query(params)),
    claim:(id:string)=>request<Claim>('/claims/'+encode(id)),
    importContent:(body:components['schemas']['ImportBody'])=>post<components['schemas']['ImportResult']>('/import',body),
    toggleFollow:(id:string)=>post<{followed:boolean}>('/authors/'+encode(id)+'/follow'),
    compare:(body:components['schemas']['CompareRequest'])=>post<Comparison>('/compare',body),
    submitReview:(id:string,note:string)=>post<{id:string;status:string}>('/claims/'+encode(id)+'/reviews',{note}),
    verify:(id:string)=>post<Job>('/claims/'+encode(id)+'/verification-jobs'),
    job:(id:string)=>request<Job>('/jobs/'+encode(id)),
    research:(body:components['schemas']['ResearchRequest'])=>post<ResearchJob>('/research-jobs',body),
    researchJob:(id:string)=>request<ResearchJob>('/research-jobs/'+encode(id)),
    retryResearch:(id:string)=>post<ResearchJob>('/research-jobs/'+encode(id)+'/retry'),
    textAudit:(body:components['schemas']['TextAuditRequest'])=>post<ResearchJob>('/text-audits',body),
    officialStatus:()=>request<{configured:boolean;provider:string;cookie_required:boolean}>('/official/status'),
    officialSearch:(body:components['schemas']['OfficialSearchRequest'])=>post<Record<string,unknown>>('/official/search',body),
    createPersona:(body:components['schemas']['AuthorRequest'])=>post<AuthorPersona>('/personas',body),
    persona:(id:string)=>request<AuthorPersona>('/personas/'+encode(id)),
    chatWithPersona:(id:string,message:string)=>post<PersonaReply>('/personas/'+encode(id)+'/chat',{message}),
    createRoom:(body:components['schemas']['RoomRequest'])=>post<DiscussionRoom>('/rooms',body),
    createDemoRoom:(council=true)=>post<DiscussionRoom>('/rooms/demo',{council}),
    room:(id:string)=>request<DiscussionRoom>('/rooms/'+encode(id)),
    sendRoomMessage:(id:string,message:string)=>post<DiscussionRoom>('/rooms/'+encode(id)+'/messages',{message}),
  };
}
