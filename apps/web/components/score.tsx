'use client';
import { useEffect, useRef } from 'react';
import type { Scorecard } from '@/lib/api';
import { EXCLUSION_LABEL, NA, num, pct } from '@/lib/format';
import { Notice } from './ui';

/** Big number that renders null as "样本不足" instead of 0. */
export function MetricValue({ value, format = pct, suffix }: { value: number | null | undefined; format?: (v: number | null | undefined) => string; suffix?: string }) {
  const text = format(value);
  const na = text === NA;
  return (
    <div className={'big-num' + (na ? ' na' : '')}>
      {text}
      {!na && suffix && <small style={{ fontSize: 14, color: 'var(--muted)', marginLeft: 4, fontFamily: 'var(--sans)' }}>{suffix}</small>}
    </div>
  );
}

export function WilsonBar({ accuracy, interval }: { accuracy: number | null; interval: number[] | null }) {
  const na = accuracy === null || !interval;
  return (
    <div className={'wilson' + (na ? ' na' : '')} role="img" aria-label={na ? '置信区间：样本不足' : `命中率 ${pct(accuracy)}，95% Wilson 区间 ${pct(interval![0])}–${pct(interval![1])}`}>
      <div className="axis" />
      {!na && (
        <>
          <div className="band" style={{ left: `${interval![0] * 100}%`, width: `${(interval![1] - interval![0]) * 100}%` }} />
          <div className="point" style={{ left: `${accuracy! * 100}%` }} />
        </>
      )}
      <div className="ticks" aria-hidden>
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
    </div>
  );
}

export function CalibrationChart({ bins }: { bins: Scorecard['probabilistic']['calibration'] }) {
  const ref = useRef<HTMLDivElement>(null);
  const total = bins.reduce((s, b) => s + b.n, 0);
  useEffect(() => {
    if (!total || !ref.current) return;
    let disposed = false;
    let chart: { dispose: () => void; resize: () => void } | undefined;
    const el = ref.current;
    const onResize = () => chart?.resize();
    (async () => {
      const echarts = await import('echarts/core');
      const [{ ScatterChart, LineChart }, { GridComponent, TooltipComponent }, { CanvasRenderer }] = await Promise.all([
        import('echarts/charts'),
        import('echarts/components'),
        import('echarts/renderers'),
      ]);
      if (disposed) return;
      echarts.use([ScatterChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer]);
      const c = echarts.init(el, undefined, { renderer: 'canvas' });
      chart = c;
      const points = bins
        .filter((b) => b.n > 0 && b.mean_probability !== null && b.observed_frequency !== null)
        .map((b) => ({ value: [b.mean_probability! * 100, b.observed_frequency! * 100, b.n], range: `${b.lower * 100}–${b.upper * 100}%` }));
      c.setOption({
        animation: false,
        grid: { left: 44, right: 16, top: 16, bottom: 40 },
        tooltip: {
          trigger: 'item',
          formatter: (p: { data: { value: number[]; range: string } }) =>
            `区间 ${p.data.range}<br/>平均给出概率 ${p.data.value[0].toFixed(0)}%<br/>实际发生频率 ${p.data.value[1].toFixed(0)}%<br/>样本 ${p.data.value[2]} 条`,
        },
        xAxis: { type: 'value', min: 0, max: 100, name: '给出的概率 %', nameLocation: 'middle', nameGap: 26, axisLine: { lineStyle: { color: '#b8b09a' } }, splitLine: { lineStyle: { color: '#ece6d6' } }, axisLabel: { color: '#5d665e' } },
        yAxis: { type: 'value', min: 0, max: 100, name: '实际发生 %', nameLocation: 'middle', nameGap: 32, axisLine: { lineStyle: { color: '#b8b09a' } }, splitLine: { lineStyle: { color: '#ece6d6' } }, axisLabel: { color: '#5d665e' } },
        series: [
          { type: 'line', data: [[0, 0], [100, 100]], symbol: 'none', lineStyle: { type: 'dashed', color: '#a59d86', width: 1 }, silent: true, tooltip: { show: false } },
          { type: 'scatter', data: points, symbolSize: (v: number[]) => Math.min(30, 8 + Math.sqrt(v[2]) * 4), itemStyle: { color: '#2f5a45', opacity: 0.85 } },
        ],
      });
      window.addEventListener('resize', onResize);
    })();
    return () => {
      disposed = true;
      window.removeEventListener('resize', onResize);
      chart?.dispose();
    };
  }, [bins, total]);
  if (!total)
    return (
      <div className="chart-empty">
        <div>
          暂无显式概率预测样本
          <br />
          <small>只有原文写明百分比的预测才会进入校准图，系统不会从语气推测概率。</small>
        </div>
      </div>
    );
  return <div ref={ref} className="chart-box" role="img" aria-label="校准曲线：横轴为给出的概率，纵轴为实际发生频率，虚线为完美校准" />;
}

function Meter({ label, value, goal, unit }: { label: string; value: number; goal: number; unit: string }) {
  const ratio = Math.min(1, goal ? value / goal : 0);
  return (
    <div className="meter-row">
      <span>{label}</span>
      <div className="meter-track" role="meter" aria-valuemin={0} aria-valuemax={goal} aria-valuenow={value} aria-label={label}>
        <div className="meter-fill" style={{ width: `${ratio * 100}%`, opacity: ratio >= 1 ? 1 : 0.55 }} />
        <span className="goal" aria-hidden />
      </div>
      <b>
        {value} / {goal} {unit}
      </b>
    </div>
  );
}

/** Answers "why can't this be ranked?" with the actual policy thresholds. */
export function CoverageMeters({ card }: { card: Scorecard }) {
  const p = card.readiness.policy;
  const c = card.coverage;
  return (
    <div className="meter">
      <Meter label="有效独立事件" value={c.scored_events} goal={p.minimum_events ?? 20} unit="个" />
      <Meter label="发表跨度" value={c.span_days} goal={p.minimum_span_days ?? 180} unit="天" />
      <Meter label="活跃月份" value={c.active_months} goal={p.minimum_active_months ?? 3} unit="月" />
    </div>
  );
}

export function ReadinessNotice({ card }: { card: Scorecard }) {
  const r = card.readiness;
  if (r.eligible_for_ranking)
    return (
      <Notice tone="ok" title="样本达到比较门槛">
        结果只代表这个领域的历史判断记录，不是资质认证。{r.pending_reviews ? `待处理纠错 ${r.pending_reviews} 条。` : ''}
      </Notice>
    );
  return (
    <Notice tone="neutral" title="不据此排名或推荐">
      {r.warnings.length > 0 && (
        <ul>
          {r.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </Notice>
  );
}

export function ScorecardPanel({ card }: { card: Scorecard }) {
  const cat = card.categorical;
  const prob = card.probabilistic;
  const eq = card.evidence_quality;
  const exclusions = Object.entries(card.exclusions).filter(([, n]) => n > 0);
  return (
    <div className="score-grid">
      <section className="card pad span-4" aria-labelledby="sc-cat">
        <div className="panel-title">
          <h3 id="sc-cat">严格命中率</h3>
          <small>明确命题 · 95% Wilson 区间</small>
        </div>
        <MetricValue value={cat.accuracy} />
        <div className="subnum">
          计分样本 {cat.n} 条{cat.n > 0 && ` · 吻合 ${cat.correct} · 落空 ${cat.wrong} · 部分 ${cat.partial}`}
        </div>
        <WilsonBar accuracy={cat.accuracy} interval={cat.wilson_95} />
      </section>

      <section className="card pad span-4" aria-labelledby="sc-prob">
        <div className="panel-title">
          <h3 id="sc-prob">概率预测 Brier</h3>
          <small>越低越好 · 基线 {card.probabilistic.baseline_brier}</small>
        </div>
        <MetricValue value={prob.brier} format={(v) => num(v, 3)} />
        <div className="subnum">
          显式概率样本 {prob.n} 条 · 相对 50% 基线技能 {prob.skill_vs_50pct === null ? NA : pct(prob.skill_vs_50pct, 1)}
        </div>
        <dl className="kv">
          <dt>Brier 与命中率</dt>
          <dd>分开计算，不混合</dd>
        </dl>
      </section>

      <section className="card pad span-4" aria-labelledby="sc-ev">
        <div className="panel-title">
          <h3 id="sc-ev">证据可追溯性</h3>
          <small>评价材料，不评价人</small>
        </div>
        <dl className="kv" style={{ marginTop: 0 }}>
          <dt>证据条数</dt>
          <dd>{eq.evidence_count}</dd>
          <dt>证据有日期</dt>
          <dd>{pct(eq.dated_evidence_ratio)}</dd>
          <dt>原始版本已存证</dt>
          <dd>{pct(eq.verified_original_ratio)}</dd>
          <dt>已确认原始出处</dt>
          <dd>{eq.confirmed_origins}</dd>
          <dt>已确认一手来源</dt>
          <dd>{eq.confirmed_primary_sources}</dd>
        </dl>
      </section>

      <section className="card pad span-6" aria-labelledby="sc-cov">
        <div className="panel-title">
          <h3 id="sc-cov">样本覆盖与比较门槛</h3>
          <small>{card.coverage.sampling_confirmed ? '已确认采样覆盖' : '尚未确认采样覆盖'}</small>
        </div>
        <CoverageMeters card={card} />
        <dl className="kv">
          <dt>收录判断</dt>
          <dd>{card.coverage.total_claims} 条</dd>
          <dt>独立事件 / 重复记录</dt>
          <dd>
            {card.coverage.independent_events} / {card.coverage.duplicate_records}
          </dd>
          {exclusions.map(([k, n]) => (
            <FragmentRow key={k} label={`未计分：${EXCLUSION_LABEL[k] ?? k}`} value={`${n} 条`} />
          ))}
        </dl>
        <div style={{ marginTop: 14 }}>
          <ReadinessNotice card={card} />
        </div>
      </section>

      <section className="card pad span-6" aria-labelledby="sc-cal">
        <div className="panel-title">
          <h3 id="sc-cal">校准曲线</h3>
          <small>说“有 70% 把握”的事，是否约七成发生</small>
        </div>
        <CalibrationChart bins={prob.calibration} />
      </section>
    </div>
  );
}

function FragmentRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
