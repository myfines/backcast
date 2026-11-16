// Display helpers. v1 ratios are 0–1; null means "not enough samples", never 0.
import type { Claim, Verdict } from './api';

export const NA = '样本不足';

export function pct(ratio: number | null | undefined, digits = 0): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return NA;
  return `${(ratio * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NA;
  return value.toFixed(digits);
}

export function day(value: string | null | undefined): string {
  if (!value) return '日期未知';
  const d = value.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d.replaceAll('-', '.') : value;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export type VerdictStatus = Verdict['status'];

/** Outcome labels describe the record, never the person. */
export const VERDICT: Record<VerdictStatus, { label: string; tone: string; hint: string }> = {
  correct: { label: '结果吻合', tone: 'correct', hint: '外部证据与所述判断一致' },
  wrong: { label: '结果落空', tone: 'wrong', hint: '外部证据与所述判断不一致' },
  partial: { label: '部分吻合', tone: 'partial', hint: '判断只有一部分被证据支持' },
  insufficient: { label: '证据不足', tone: 'muted', hint: '尚无足够证据作出判定' },
  pending: { label: '尚未到期', tone: 'pending', hint: '预测窗口尚未结束' },
  unverifiable: { label: '不可验证', tone: 'muted', hint: '缺少客观检验标准或明确截止日' },
};

/** Fact statements are checked against evidence, not against an outcome, so they get their own wording. */
export const FACT_VERDICT: Partial<Record<VerdictStatus, { label: string; hint: string }>> = {
  correct: { label: '有证据支持', hint: '取得的外部证据支持这条事实陈述' },
  wrong: { label: '证据与之不符', hint: '取得的外部证据与这条事实陈述不一致' },
  partial: { label: '部分有证据支持', hint: '证据只支持这条陈述的一部分' },
};

export function verdictView(status: VerdictStatus, kind?: string) {
  const base = VERDICT[status] ?? { label: status, tone: 'muted', hint: '' };
  const fact = kind === 'fact' ? FACT_VERDICT[status] : undefined;
  return fact ? { ...base, ...fact } : base;
}

export const KIND: Record<Claim['kind'], string> = { prediction: '预测', fact: '事实陈述', opinion: '观点' };

export const SOURCE_TYPE: Record<string, string> = { primary: '一手来源', secondary: '二手转述', unknown: '来源类型未确认' };

export const AUTHOR_TYPE: Record<string, string> = { 个人: '个人档案', 机构: '机构档案', 待确认: '身份待确认' };

export const AUDIT_ACTION: Record<string, string> = {
  author_created: '建立档案',
  claim_created: '收录判断',
  source_imported: '导入原始材料',
  review_requested: '提交纠错',
  follow_changed: '关注状态变化',
  verified: '检索核验',
  verification_job_finished: '核验任务结束',
  manual_resolution: '人工裁定',
  evidence_metadata_reviewed: '证据出处标注',
  sampling_reviewed: '采样声明',
  history_materials_collected: '收录调查材料',
  research_analysis_completed: '完成材料核查',
};

export const JOB_STATUS: Record<string, string> = { queued: '排队中', running: '检索与核验中', succeeded: '核验流程已结束', failed: '核验失败' };

export const POLICY_LABEL: Record<string, string> = {
  minimum_events: '最少独立事件',
  minimum_span_days: '最短发表跨度（天）',
  minimum_active_months: '最少活跃月份',
  minimum_paired_events: '对比所需共同事件',
  calibration_bins: '校准分箱数',
};

export const EXCLUSION_LABEL: Record<string, string> = {
  not_prediction: '不是预测',
  unidentified_event: '未标注独立事件',
  unverified_original: '原始版本未存证',
  missing_time: '缺少发表或截止时间',
  not_due: '尚未到期',
  not_before_event: '发表不早于事件',
  late_edit: '事后编辑过',
  future_outcome: '结果晚于截止日视图',
  no_citations: '判定没有引用',
  invalid_citation: '引用无效',
  undated_evidence: '证据无日期',
  future_evidence: '证据晚于截止日视图',
  invalid_probability_or_outcome: '概率或结果无效',
  unresolved: '尚无判定结果',
};

export function initials(name: string, given?: string) {
  if (given) return given;
  const latin = name.match(/[A-Za-z]+/g);
  if (latin && latin.length >= 2) return (latin[0][0] + latin[1][0]).toUpperCase();
  return name.slice(0, 1);
}

export function today() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const RESEARCH_STATUS: Record<string, { label: string; tone: 'info' | 'ok' | 'warn' | 'error' | 'neutral'; active: boolean; terminal: boolean }> = {
  queued: { label: '排队中', tone: 'info', active: true, terminal: false },
  collecting: { label: '正在采集', tone: 'info', active: true, terminal: false },
  needs_login: { label: '需要先登录知乎', tone: 'warn', active: false, terminal: true },
  blocked: { label: '知乎拒绝了请求', tone: 'warn', active: false, terminal: true },
  awaiting_analysis: { label: '材料已收集，等待分析', tone: 'info', active: false, terminal: false },
  analyzing: { label: '正在分析', tone: 'info', active: true, terminal: false },
  succeeded: { label: '已完成', tone: 'ok', active: false, terminal: true },
  failed: { label: '没有完成', tone: 'error', active: false, terminal: true },
};

export const CAPTURE_METHOD: Record<string, string> = {
  'pyzhihu-cli-web-api': '按答主历史列表采集',
  operator_supplied_public_excerpt: '人工提供的公开节选',
};

export const PROVENANCE: Record<string, string> = {
  worker_declared: '由外部分析器自报，后端只校验了原文和引用',
  configured_api: '由后端配置的模型接口生成',
};
