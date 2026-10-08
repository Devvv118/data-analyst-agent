export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function fetchBoot(signal) {
  const res = await fetch(`${API_URL}/boot`, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// POST /api/stream (multipart) -> newline-delimited JSON; onEvent() is called as each line arrives.
// Same form the backend already expects: a "questions" text field + one field per data file (named after the file).
export async function streamAnalyze({ questions, files }, onEvent, signal) {
  const body = new FormData();
  body.append("questions", questions);
  for (const f of files) body.append(f.name, f);

  const res = await fetch(`${API_URL}/api/stream`, { method: "POST", body, signal });

  if (!res.ok || !res.body) {
    let detail;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : j.message ?? JSON.stringify(j.detail ?? j);
    } catch { /* not JSON */ }
    throw new Error(detail ?? `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
  if (buf.trim()) onEvent(JSON.parse(buf));
}

export const formatBytes = (n) =>
  n < 1024 ? `${n} B` : n < 1024 ** 2 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 ** 2).toFixed(1)} MB`;
