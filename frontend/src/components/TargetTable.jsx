import { EMPTY_TARGET } from "../example";

const COLUMNS = [
  { key: "id", label: "编号", type: "text", width: "7rem" },
  { key: "azimuth", label: "方位角°", type: "number" },
  { key: "elevation", label: "俯仰角°", type: "number" },
  { key: "duration", label: "持续秒", type: "number" },
  { key: "window_start", label: "窗口开始", type: "number" },
  { key: "window_end", label: "窗口结束", type: "number" },
  { key: "priority", label: "优先级", type: "number" },
];

export default function TargetTable({ targets, onChange }) {
  const update = (index, key, value) => {
    const next = targets.map((t, i) => (i === index ? { ...t, [key]: value } : t));
    onChange(next);
  };

  const remove = (index) => onChange(targets.filter((_, i) => i !== index));

  const add = () => {
    if (targets.length >= 16) return;
    const used = new Set(targets.map((t) => t.id));
    let n = targets.length + 1;
    while (used.has(`T${n}`)) n += 1;
    onChange([...targets, { ...EMPTY_TARGET, id: `T${n}` }]);
  };

  return (
    <section className="card">
      <div className="card-header">
        <h2>观测目标（{targets.length}/16）</h2>
        <button type="button" onClick={add} disabled={targets.length >= 16}>
          + 添加目标
        </button>
      </div>
      <div className="table-scroll">
        <table className="target-table">
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c.key}>{c.label}</th>
              ))}
              <th>必观</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {targets.map((t, i) => (
              <tr key={i}>
                {COLUMNS.map((c) => (
                  <td key={c.key}>
                    <input
                      type={c.type}
                      style={c.width ? { width: c.width } : undefined}
                      value={t[c.key]}
                      onChange={(e) => update(i, c.key, e.target.value)}
                    />
                  </td>
                ))}
                <td className="center">
                  <input
                    type="checkbox"
                    checked={t.mandatory}
                    onChange={(e) => update(i, "mandatory", e.target.checked)}
                  />
                </td>
                <td className="center">
                  <button
                    type="button"
                    className="danger"
                    title="删除该目标"
                    onClick={() => remove(i)}
                    disabled={targets.length <= 2}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">目标数量须为 2–16 个；时间均为当天整数秒（0–86399），角度为整数度。</p>
    </section>
  );
}
