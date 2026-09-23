import { useEffect, useState } from "react";
import { fetchSchedule } from "./api";
import { EXAMPLE_INPUT } from "./example";
import { fmtLoc } from "./format";
import ImportExport from "./components/ImportExport";
import InitialPanel from "./components/InitialPanel";
import ResultView from "./components/ResultView";
import TargetTable from "./components/TargetTable";

const TARGET_KEYS = [
  "id",
  "azimuth",
  "elevation",
  "duration",
  "window_start",
  "window_end",
  "priority",
  "mandatory",
];

function parseNumber(label, raw, { integer = false } = {}) {
  if (raw === "" || raw === null || raw === undefined) {
    throw new Error(`${label} 不能为空`);
  }
  const value = Number(raw);
  if (!Number.isFinite(value) || (integer && !Number.isInteger(value))) {
    throw new Error(`${label} 必须是${integer ? "整数" : "数字"}，当前为「${raw}」`);
  }
  return value;
}

function buildPayload(initial, speeds, targets) {
  return {
    initial: {
      time: parseNumber("初始时刻", initial.time, { integer: true }),
      azimuth: parseNumber("初始方位角", initial.azimuth, { integer: true }),
      elevation: parseNumber("初始俯仰角", initial.elevation, { integer: true }),
    },
    azimuth_speed: parseNumber("方位转速", speeds.azimuth_speed),
    elevation_speed: parseNumber("俯仰转速", speeds.elevation_speed),
    targets: targets.map((t, i) => ({
      id: String(t.id),
      azimuth: parseNumber(`目标 ${t.id || i + 1} 的方位角`, t.azimuth, { integer: true }),
      elevation: parseNumber(`目标 ${t.id || i + 1} 的俯仰角`, t.elevation, { integer: true }),
      duration: parseNumber(`目标 ${t.id || i + 1} 的持续秒数`, t.duration, { integer: true }),
      window_start: parseNumber(`目标 ${t.id || i + 1} 的窗口开始`, t.window_start, { integer: true }),
      window_end: parseNumber(`目标 ${t.id || i + 1} 的窗口结束`, t.window_end, { integer: true }),
      priority: parseNumber(`目标 ${t.id || i + 1} 的优先级`, t.priority, { integer: true }),
      mandatory: Boolean(t.mandatory),
    })),
  };
}

/** Normalize an imported object into form state; throws on bad shape. */
function importToForm(obj) {
  if (!obj || typeof obj !== "object") throw new Error("导入内容必须是 JSON 对象");
  const { initial, azimuth_speed, elevation_speed, targets } = obj;
  if (!initial || typeof initial !== "object") throw new Error("缺少 initial 对象");
  for (const key of ["time", "azimuth", "elevation"]) {
    if (!(key in initial)) throw new Error(`initial 缺少字段 ${key}`);
  }
  if (azimuth_speed === undefined || elevation_speed === undefined) {
    throw new Error("缺少 azimuth_speed / elevation_speed");
  }
  if (!Array.isArray(targets) || targets.length < 2 || targets.length > 16) {
    throw new Error("targets 必须是 2–16 个目标的数组");
  }
  const rows = targets.map((t, i) => {
    if (!t || typeof t !== "object") throw new Error(`第 ${i + 1} 个目标不是对象`);
    for (const key of TARGET_KEYS) {
      if (!(key in t)) throw new Error(`第 ${i + 1} 个目标缺少字段 ${key}`);
    }
    return {
      id: String(t.id),
      azimuth: String(t.azimuth),
      elevation: String(t.elevation),
      duration: String(t.duration),
      window_start: String(t.window_start),
      window_end: String(t.window_end),
      priority: String(t.priority),
      mandatory: Boolean(t.mandatory),
    };
  });
  return {
    initial: {
      time: String(initial.time),
      azimuth: String(initial.azimuth),
      elevation: String(initial.elevation),
    },
    speeds: { azimuth_speed: String(azimuth_speed), elevation_speed: String(elevation_speed) },
    targets: rows,
  };
}

export default function App() {
  const [initial, setInitial] = useState(EXAMPLE_INPUT.initial);
  const [speeds, setSpeeds] = useState({
    azimuth_speed: EXAMPLE_INPUT.azimuth_speed,
    elevation_speed: EXAMPLE_INPUT.elevation_speed,
  });
  const [targets, setTargets] = useState(EXAMPLE_INPUT.targets);
  const [result, setResult] = useState(null);
  const [fieldErrors, setFieldErrors] = useState([]);
  const [localError, setLocalError] = useState(null);
  const [loading, setLoading] = useState(false);

  // 输入一旦变化，撤下旧结果与旧错误
  useEffect(() => {
    setResult(null);
    setFieldErrors([]);
    setLocalError(null);
  }, [initial, speeds, targets]);

  const handleImport = (obj) => {
    try {
      const form = importToForm(obj);
      setInitial(form.initial);
      setSpeeds(form.speeds);
      setTargets(form.targets);
      return null;
    } catch (err) {
      return err.message;
    }
  };

  const handleExample = () => {
    handleImport(EXAMPLE_INPUT);
  };

  const handleExport = () => {
    let payload;
    try {
      payload = buildPayload(initial, speeds, targets);
    } catch (err) {
      setLocalError(err.message);
      return;
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "observation-input.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSubmit = async () => {
    let payload;
    try {
      payload = buildPayload(initial, speeds, targets);
    } catch (err) {
      setLocalError(err.message);
      return;
    }
    setLoading(true);
    const { httpStatus, body, networkError } = await fetchSchedule(payload);
    setLoading(false);
    if (networkError) {
      setLocalError(`无法连接后端服务：${networkError}`);
      return;
    }
    if (httpStatus === 200 && body) {
      setResult(body);
      return;
    }
    if (httpStatus === 422 && body && Array.isArray(body.detail)) {
      setFieldErrors(body.detail.map((e) => ({ path: fmtLoc(e.loc), msg: e.msg })));
      return;
    }
    setLocalError(`服务返回异常（HTTP ${httpStatus}）`);
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>射电观测排程台</h1>
        <p>夜间观测全局最优排程：必观目标全部入选，依次最大化总优先级与目标数，再最小化结束时刻。</p>
      </header>

      <main className="layout">
        <div className="panel-left">
          <InitialPanel
            initial={initial}
            speeds={speeds}
            onInitialChange={setInitial}
            onSpeedsChange={setSpeeds}
          />
          <TargetTable targets={targets} onChange={setTargets} />
          <ImportExport onImport={handleImport} onExport={handleExport} onExample={handleExample} />
          <button type="button" className="submit" onClick={handleSubmit} disabled={loading}>
            {loading ? "排程中…" : "开始排程"}
          </button>
          {localError && <p className="error-text">{localError}</p>}
          {fieldErrors.length > 0 && (
            <div className="error-box">
              <strong>输入校验未通过：</strong>
              <ul>
                {fieldErrors.map((e, i) => (
                  <li key={i}>
                    <code>{e.path || "请求体"}</code>：{e.msg}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="panel-right">
          {result ? (
            <ResultView result={result} targets={targets} />
          ) : (
            <section className="card placeholder">
              <h2>排程结果</h2>
              <p className="hint">编辑或导入参数后点击「开始排程」，此处将展示等待、转向、观测时间线与未选目标。</p>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
