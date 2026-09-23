export function fmtTime(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = String(Math.floor(s / 3600)).padStart(2, "0");
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  return `${h}:${m}:${sec}`;
}

export function fmtDur(seconds) {
  return `${seconds} 秒`;
}

/** Format a FastAPI/Pydantic error loc array as a readable field path. */
export function fmtLoc(loc) {
  if (!Array.isArray(loc)) return "";
  return loc
    .filter((part) => part !== "body")
    .map((part) => (typeof part === "number" ? `[${part}]` : `.${part}`))
    .join("")
    .replace(/^\./, "");
}
