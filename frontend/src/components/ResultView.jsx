import { useState } from "react";
import Markdown from "./Markdown";

const isImage = (v) => typeof v === "string" && v.startsWith("data:image/");

// keep base64 blobs out of the readable JSON view
const shorten = (_k, v) => (typeof v === "string" && v.startsWith("data:") && v.length > 80 ? `${v.slice(0, 32)}…(${v.length.toLocaleString()} chars)` : v);
const pretty = (v) => JSON.stringify(v, shorten, 2);

function tryParse(text) {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false };
  }
}

function Item({ value }) {
  if (isImage(value))
    return <img src={value} alt="generated chart" className="mt-1 max-w-full rounded-lg border border-white/10 bg-white p-1" />;
  if (value !== null && typeof value === "object")
    return <pre className="mt-1 overflow-x-auto rounded-xl bg-black/40 p-3 text-[12.5px] leading-relaxed text-cream/85">{pretty(value)}</pre>;
  return <span className="break-words whitespace-pre-wrap text-cream">{String(value)}</span>;
}

export default function ResultView({ output }) {
  const [copied, setCopied] = useState(false);
  const parsed = tryParse(output);
  const data = parsed.ok ? parsed.value : null;
  const structured = parsed.ok && data !== null && typeof data === "object";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };

  let body;
  if (Array.isArray(data)) {
    body = (
      <ol className="mt-4 space-y-3 text-[14px] leading-relaxed">
        {data.map((v, i) => (
          <li key={i} className="flex gap-3">
            <span className="tabular w-6 shrink-0 text-right text-gold">{i + 1}.</span>
            <div className="min-w-0 flex-1">
              <Item value={v} />
            </div>
          </li>
        ))}
      </ol>
    );
  } else if (structured) {
    body = (
      <dl className="mt-4 space-y-3 text-[14px] leading-relaxed">
        {Object.entries(data).map(([k, v]) => (
          <div key={k} className="flex flex-col gap-1 md:flex-row md:gap-4">
            <dt className="shrink-0 break-words text-gold-soft md:w-56">{k}</dt>
            <dd className="min-w-0 flex-1">
              <Item value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  } else if (parsed.ok && typeof data !== "string") {
    body = <p className="mt-4 text-[14px] text-cream">{String(data)}</p>;
  } else {
    // plain text / markdown (e.g. the model's best-effort answer)
    body = <Markdown source={parsed.ok ? data : output} />;
  }

  return (
    <>
      {body}
      {structured && (
        <details className="group mt-6 text-[12px]">
          <summary className="flex cursor-pointer list-none items-baseline gap-4 text-white/35 marker:hidden hover:text-gold">
            <span className="group-open:hidden">+ raw json</span>
            <span className="hidden group-open:inline">- raw json</span>
          </summary>
          <div className="mt-3">
            <button type="button" onClick={copy} className="mb-2 text-gold underline-offset-4 hover:text-gold-soft hover:underline">
              {copied ? "[ copied ]" : "[ copy full output ]"}
            </button>
            <pre className="max-h-96 overflow-auto rounded-xl bg-black/40 p-4 leading-relaxed text-cream/75">{pretty(data)}</pre>
          </div>
        </details>
      )}
    </>
  );
}
