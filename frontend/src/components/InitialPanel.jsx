export default function InitialPanel({ initial, speeds, onInitialChange, onSpeedsChange }) {
  const setInitial = (key) => (e) => onInitialChange({ ...initial, [key]: e.target.value });
  const setSpeed = (key) => (e) => onSpeedsChange({ ...speeds, [key]: e.target.value });

  return (
    <section className="card">
      <h2>初始状态与转速</h2>
      <div className="field-grid">
        <label>
          初始时刻（秒）
          <input type="number" min="0" max="86399" value={initial.time} onChange={setInitial("time")} />
        </label>
        <label>
          初始方位角（度）
          <input type="number" min="0" max="359" value={initial.azimuth} onChange={setInitial("azimuth")} />
        </label>
        <label>
          初始俯仰角（度）
          <input type="number" min="0" max="90" value={initial.elevation} onChange={setInitial("elevation")} />
        </label>
        <label>
          方位转速（度/秒）
          <input type="number" min="0" step="any" value={speeds.azimuth_speed} onChange={setSpeed("azimuth_speed")} />
        </label>
        <label>
          俯仰转速（度/秒）
          <input type="number" min="0" step="any" value={speeds.elevation_speed} onChange={setSpeed("elevation_speed")} />
        </label>
      </div>
    </section>
  );
}
