import { useEffect, useRef, useState } from "react";
import { formatBytes } from "../lib/api";
import { Prompt } from "./Terminal";

const MAX_QUESTIONS = 20_000;

export default function AnalyzeForm({ disabled, busy, onSubmit, onInterrupt }) {
  const [questions, setQuestions] = useState("");
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [note, setNote] = useState("");
  const taRef = useRef(null);
  const pickRef = useRef(null);

  const locked = disabled || busy;
  const canRun = !locked && questions.trim() !== "";

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 420)}px`;
  }, [questions]);

  useEffect(() => {
    if (!disabled && !busy) taRef.current?.focus({ preventScroll: true });
  }, [disabled, busy]);

  // the backend names each upload after the file, so two files with one name would overwrite each other
  const addFiles = (list) => {
    const incoming = Array.from(list);
    setFiles((cur) => {
      const names = new Set(cur.map((f) => f.name));
      const fresh = incoming.filter((f) => !names.has(f.name));
      setNote(fresh.length < incoming.length ? "skipped a file with a name that is already attached" : "");
      return [...cur, ...fresh];
    });
  };

  const run = () => {
    if (!canRun) return;
    onSubmit({ questions: questions.trim(), files });
    setQuestions("");
    setFiles([]);
    setNote("");
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !e.nativeEvent.isComposing) {
      e.preventDefault();
      run();
    }
  };

  return (
    <section className="mt-10">
      <Prompt>analyze</Prompt>

      <label className="mt-3 flex items-start gap-3 text-[13px]">
        <span className="w-[5.5rem] shrink-0 pt-[3px] text-gold-soft">questions</span>
        <span className="pt-[3px] text-gold">▸</span>
        <textarea
          ref={taRef}
          rows={3}
          value={questions}
          maxLength={MAX_QUESTIONS}
          disabled={locked}
          onChange={(e) => setQuestions(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={disabled ? "waiting for the backend ..." : "Describe the analysis you want, and the format of the answer ..."}
          spellCheck={false}
          className="min-w-0 flex-1 resize-none border-b border-dashed border-white/20 bg-transparent py-0.5 leading-relaxed text-cream caret-gold outline-none transition-colors placeholder:text-white/25 focus:border-gold disabled:opacity-50"
        />
      </label>

      <div
        className="mt-4 flex items-start gap-3 text-[13px]"
        onDragOver={(e) => {
          e.preventDefault();
          if (!locked) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!locked) addFiles(e.dataTransfer.files);
        }}
      >
        <span className="w-[5.5rem] shrink-0 pt-[3px] text-gold-soft">
          files <span className="text-white/30">(opt)</span>
        </span>
        <span className="pt-[3px] text-gold">▸</span>
        <div
          className={`min-w-0 flex-1 border-b border-dashed py-0.5 transition-colors ${
            dragging ? "border-gold bg-gold/5" : "border-white/20"
          }`}
        >
          {files.length > 0 && (
            <ul className="mb-2 space-y-1">
              {files.map((f) => (
                <li key={f.name} className="line-in flex items-baseline gap-3 text-[12.5px]">
                  <span className="min-w-0 break-all text-cream">{f.name}</span>
                  <span className="shrink-0 text-white/35">{formatBytes(f.size)}</span>
                  {!locked && (
                    <button
                      type="button"
                      onClick={() => setFiles((cur) => cur.filter((x) => x !== f))}
                      className="shrink-0 text-white/35 transition-colors hover:text-term-red"
                      aria-label={`remove ${f.name}`}
                    >
                      ✕
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <input
            ref={pickRef}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            disabled={locked}
            onClick={() => pickRef.current?.click()}
            className="text-gold underline-offset-4 transition-colors hover:text-gold-soft hover:underline disabled:cursor-not-allowed disabled:opacity-40"
          >
            [ + attach files ]
          </button>
          <span className="ml-3 text-[11px] text-white/30">or drop them here · csv, json, txt, html, images</span>
        </div>
      </div>

      {note && <p className="mt-2 pl-[7.1rem] text-[12px] text-gold-soft">! {note}</p>}

      <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3 pl-0 md:pl-[7.1rem]">
        {busy ? (
          <button
            type="button"
            onClick={onInterrupt}
            className="rounded-full border border-term-red/60 px-5 py-2.5 text-[11px] tracking-[0.08em] text-term-red transition-colors hover:bg-term-red/10"
          >
            ^C INTERRUPT
          </button>
        ) : (
          <button
            type="button"
            onClick={run}
            disabled={!canRun}
            className="rounded-full border border-gold bg-gold px-5 py-2.5 text-[11px] tracking-[0.08em] text-warm-ink transition-colors hover:bg-gold-soft disabled:cursor-not-allowed disabled:border-white/15 disabled:bg-transparent disabled:text-white/30"
          >
            RUN ⏎
          </button>
        )}
        <span className="text-[11px] text-white/35">
          ctrl+enter to run · {questions.length.toLocaleString()}/{MAX_QUESTIONS.toLocaleString()}
        </span>
      </div>
    </section>
  );
}
