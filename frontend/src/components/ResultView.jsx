import { fmtDur, fmtTime } from "../format";

const SEGMENTS = [
  { key: "slew", label: "转向", className: "seg-slew" },
  { key: "wait", label: "等待", className: "seg-wait" },
  { key: "observe", label: "观测", className: "seg-observe" },
];

function Timeline({ steps, rangeStart, rangeEnd }) {
  const span = Math.max(1, rangeEnd - rangeStart);
  const pct = (t) => `${(((t - rangeStart) / span) * 100).toFixed(3)}%`;
  const ticks = Array.from({ length: 5 }, (_, i) => rangeStart + (span * i) / 4);

  return (
    <div className="timeline">
      <div className="timeline-legend">
        {SEGMENTS.map((s) => (
          <span key={s.key} className="legend-item">
            <i className={`legend-swatch ${s.className}`} />
            {s.label}
          </span>
        ))}
      </div>
      <div className="timeline-rows">
        {steps.map((step) => (
          <div className="timeline-row" key={step.target_id}>
            <div className="timeline-label" title={step.target_id}>
              {step.target_id}
            </div>
            <div className="timeline-track">
              {SEGMENTS.map(({ key, className }) => {
                const phase = step[key];
                if (phase.end <= phase.start) return null;
                return (
                  <div
                    key={key}
                    className={`timeline-seg ${className}`}
                    style={{ left: pct(phase.start), width: pct(phase.end - phase.start) }}
                    title={`${step.target_id} ${key}: ${fmtTime(phase.start)}–${fmtTime(phase.end)}`}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="timeline-axis">
        {ticks.map((t, i) => (
          <span key={i}>{fmtTime(Math.round(t))}</span>
        ))}
      </div>
    </div>
  );
}

export default function ResultView({ result, targets }) {
  if (!result) return null;

  if (result.status === "infeasible") {
    return (
      <section className="card result">
        <h2>排程结果</h2>
        <div className="banner banner-infeasible">
          无可行必观序列：{result.detail || "所有必观目标无法全部安排。"}
        </div>
        {result.unselected && result.unselected.length > 0 && (
          <p className="unselected-line">
            未选目标：
            {result.unselected.map((id) => (
              <span key={id} className="chip chip-muted">
                {id}
              </span>
            ))}
          </p>
        )}
      </section>
    );
  }

  const { objective, steps, unselected } = result;
  const windows = Object.fromEntries(
    targets.map((t) => [t.id, `${fmtTime(Number(t.window_start))}–${fmtTime(Number(t.window_end))}`])
  );

  return (
    <section className="card result">
      <h2>排程结果</h2>
      <div className="objective-cards">
        <div className="objective-card">
          <div className="objective-value">{objective.total_priority}</div>
          <div className="objective-label">总优先级</div>
        </div>
        <div className="objective-card">
          <div className="objective-value">{objective.target_count}</div>
          <div className="objective-label">观测目标数</div>
        </div>
        <div className="objective-card">
          <div className="objective-value">{fmtTime(objective.end_time)}</div>
          <div className="objective-label">结束时刻（{objective.end_time} 秒）</div>
        </div>
      </div>

      {steps.length > 0 ? (
        <>
          <Timeline
            steps={steps}
            rangeStart={steps[0].slew.start}
            rangeEnd={objective.end_time}
          />
          <div className="table-scroll">
            <table className="steps-table">
              <thead>
                <tr>
                  <th>目标</th>
                  <th>转向</th>
                  <th>等待</th>
                  <th>观测</th>
                  <th>可见窗</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((s) => (
                  <tr key={s.target_id}>
                    <td className="mono">{s.target_id}</td>
                    <td>
                      {fmtTime(s.slew.start)}–{fmtTime(s.slew.end)}（{fmtDur(s.slew.end - s.slew.start)}）
                    </td>
                    <td>{s.wait.end > s.wait.start ? fmtDur(s.wait.end - s.wait.start) : "—"}</td>
                    <td>
                      {fmtTime(s.observe.start)}–{fmtTime(s.observe.end)}（{fmtDur(s.observe.end - s.observe.start)}）
                    </td>
                    <td className="mono">{windows[s.target_id] || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="hint">空计划：当前条件下没有任何目标可在窗口内完成观测。</p>
      )}

      {unselected && unselected.length > 0 && (
        <p className="unselected-line">
          未选目标：
          {unselected.map((id) => (
            <span key={id} className="chip chip-muted">
              {id}
            </span>
          ))}
        </p>
      )}
    </section>
  );
}
