import { useRef, useState } from "react";

/**
 * Import (file or pasted JSON), export and example loading.
 * onImport(object) must return null on success or an error message string.
 */
export default function ImportExport({ onImport, onExport, onExample }) {
  const fileRef = useRef(null);
  const [showPaste, setShowPaste] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [error, setError] = useState(null);

  const apply = (text) => {
    let obj;
    try {
      obj = JSON.parse(text);
    } catch (err) {
      setError(`JSON 解析失败：${err.message}`);
      return;
    }
    const err = onImport(obj);
    setError(err || null);
    if (!err) {
      setShowPaste(false);
      setPasteText("");
    }
  };

  const onFile = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => apply(String(reader.result));
    reader.onerror = () => setError("文件读取失败");
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <section className="card">
      <h2>导入 / 导出</h2>
      <div className="button-row">
        <button type="button" onClick={() => fileRef.current && fileRef.current.click()}>
          导入 JSON 文件
        </button>
        <button type="button" onClick={() => setShowPaste((v) => !v)}>
          {showPaste ? "收起粘贴区" : "粘贴 JSON 导入"}
        </button>
        <button type="button" onClick={onExport}>
          导出当前输入
        </button>
        <button type="button" onClick={onExample}>
          载入示例
        </button>
        <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={onFile} />
      </div>
      {showPaste && (
        <div className="paste-area">
          <textarea
            rows="8"
            placeholder='{"initial":{"time":0,"azimuth":0,"elevation":0},"azimuth_speed":1,"elevation_speed":1,"targets":[...]}'
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
          <button type="button" onClick={() => apply(pasteText)}>
            解析并导入
          </button>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}
