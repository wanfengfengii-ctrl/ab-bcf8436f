export async function fetchSchedule(payload) {
  let resp;
  try {
    resp = await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    return { httpStatus: 0, body: null, networkError: String(err) };
  }
  let body = null;
  try {
    body = await resp.json();
  } catch {
    /* non-JSON response */
  }
  return { httpStatus: resp.status, body, networkError: null };
}
