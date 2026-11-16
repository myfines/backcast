'use client';
import { ExternalLink } from 'lucide-react';
import { api } from '@/lib/api';
import { useApi } from '@/lib/useApi';
import { POLICY_LABEL } from '@/lib/format';
import { ErrorState, Notice, Skeleton } from '@/components/ui';

const METRIC: Record<string, [string, string]> = {
  exact_accuracy: ['严格命中率', '只统计有明确截止日、原始版本已存证、证据有日期且被引用的独立事件。'],
  wilson_95: ['Wilson 95% 区间', '小样本时命中率波动很大；区间越宽，说明越不能下结论。'],
  brier: ['Brier 分数', '只用于原文写明百分比的预测：(概率 − 结果)² 的平均，越低越好；50% 基线为 0.25。'],
  calibration: ['校准', '把预测按概率分箱，看“说七成的事”是否约七成发生。'],
  traceability: ['可追溯性', '证据是否有日期、是否确认原始出处与一手来源——描述材料质量，不评价人。'],
  sampling_coverage: ['采样覆盖', '是否完整收录某段时间内的全部判断，避免只挑成功案例。'],
};

export function Methodology() {
  const m = useApi('methodology', api.methodology);
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">How we evaluate</div>
          <h1 className="page-title">评价方法</h1>
          <p className="lede">Backcast 评价的是“某个领域里，过去的判断后来怎么样了”。它不是资质认证，也不是人品评分。</p>
        </div>
      </header>

      {m.error ? (
        <ErrorState error={m.error} retry={m.reload} />
      ) : !m.data ? (
        <Skeleton h={300} />
      ) : (
        <div style={{ display: 'grid', gap: 20 }}>
          <div className="two-col">
            <section className="card pad" aria-labelledby="m-metrics">
              <div className="panel-title">
                <h2 id="m-metrics" className="section-title" style={{ fontSize: 18 }}>
                  我们看什么
                </h2>
                <span className="mono muted">{m.data.version}</span>
              </div>
              <dl style={{ display: 'grid', gap: 14, margin: 0 }}>
                {m.data.metrics.map((k) => (
                  <div key={k}>
                    <dt style={{ fontWeight: 600 }}>{METRIC[k]?.[0] ?? k}</dt>
                    <dd style={{ margin: '2px 0 0', color: 'var(--ink-2)', fontSize: 14 }}>{METRIC[k]?.[1] ?? ''}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <div style={{ display: 'grid', gap: 20 }}>
              <section className="card pad" aria-labelledby="m-policy">
                <h2 id="m-policy" className="section-title" style={{ fontSize: 18, marginBottom: 10 }}>
                  比较与排名门槛
                </h2>
                <dl className="kv" style={{ marginTop: 0, fontSize: 14 }}>
                  {Object.entries(m.data.policy).map(([k, v]) => (
                    <div key={k} style={{ display: 'contents' }}>
                      <dt>{POLICY_LABEL[k] ?? k}</dt>
                      <dd className="tnum">{v}</dd>
                    </div>
                  ))}
                </dl>
                <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
                  未达门槛时只展示记录与样本量，不显示名次或“推荐专家”。存在待处理纠错时，排名资格暂停。
                </p>
              </section>

              <section className="card pad" aria-labelledby="m-excluded">
                <h2 id="m-excluded" className="section-title" style={{ fontSize: 18, marginBottom: 10 }}>
                  我们刻意不做
                </h2>
                <ul className="list-plain">
                  {m.data.excluded.map((x) => (
                    <li key={x}>— {x}</li>
                  ))}
                </ul>
              </section>
            </div>
          </div>

          <Notice tone="info" title="为什么现在的严格成绩都是“样本不足”？">
            内置案例是注明来源的人工转述，每位预测者只有少量记录，且原始历史版本尚未独立存证。它们可以用来复盘，但不计入严格预测成绩——这是方法要求，不是数据缺失。
          </Notice>

          <section className="card pad" aria-labelledby="m-ref">
            <h2 id="m-ref" className="section-title" style={{ fontSize: 18, marginBottom: 10 }}>
              参考的开源方案
            </h2>
            <ul className="list-plain">
              {m.data.references.map((r) => (
                <li key={r}>
                  <a href={r} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--accent)' }}>
                    {r.replace('https://github.com/', '')} <ExternalLink size={12} aria-hidden style={{ display: 'inline' }} />
                  </a>
                </li>
              ))}
            </ul>
            <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
              标准概率统计公式由本项目独立实现。详细说明见仓库 <span className="mono">{m.data.details}</span>。
            </p>
          </section>
        </div>
      )}
    </>
  );
}
