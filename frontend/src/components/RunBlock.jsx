import { useEffect, useRef, useState } from "react";
import LogLine from "./LogLine";
import ResultView from "./ResultView";
import { Caret, Prompt, Spinner } from "./Terminal";

function Elapsed({ since }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="tabular text-white/30">{Math.floor((now - since) / 1000)}s</span>;
}

// One analysis: echoed command -> streamed log lines -> answer -> exit code.
export default function RunBlock({ run }) {
  const { questions, files, startedAt, lines, status, output, error, duration } = run;
  const answerRef = useRef(null);

  // bring the answer to the top of the screen as soon as it arrives
  useEffect(() => {
    if (status === "done") answerRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [status]);

  return (
    <section className="mt-10 border-t border-white/10 pt-8">
      <Prompt>
        analyze <span className="text-gold-soft">--questions</span>{" "}
        <span className="whitespace-pre-wrap text-cream">"{questions}"</span>
        {files.map((f) => (
          <span key={f.name}>
            {" "}
            <span className="text-gold-soft">--file</span> <span className="text-cream">{f.name}</span>
          </span>
        ))}
      </Prompt>

      <div className="mt-4 space-y-1">
        {lines.map((l, i) => (
          <LogLine key={i} scope="agent" {...l} />
        ))}
        {status === "running" && (
          <div className="flex gap-2 text-[12.5px] text-white/40">
            <span className="w-[8.5rem] shrink-0 max-sm:hidden" />
            <span className="w-3 shrink-0 text-center">
              <Spinner />
            </span>
            <span>
              working <Caret /> <Elapsed since={startedAt} />
            </span>
          </div>
        )}
      </div>

      {status === "done" && (
        <div ref={answerRef} className="line-in mt-8 scroll-mt-6">
          <h2 className="font-warm-display text-[11px] tracking-[0.18em] text-gold uppercase">Answer</h2>
          <ResultView output={output} />
        </div>
      )}

      {status !== "running" && (
        <p className={`mt-6 text-[11px] ${status === "done" ? "text-white/35" : "text-term-red/80"}`}>
          {status === "done" && `process exited with code 0 · ${duration?.toFixed(1)}s`}
          {status === "error" && `process exited with code 1${error?.status ? ` · http ${error.status}` : ""}`}
          {status === "aborted" && "^C"}
        </p>
      )}
    </section>
  );
}
