import { useEffect, useState } from "react";

const STATUS = {
  connecting: { dot: "bg-gold animate-pulse", label: "connecting" },
  ready: { dot: "bg-term-green", label: "connected" },
  offline: { dot: "bg-term-red", label: "offline" },
};

// Window chrome: same three dots + path bar as the portfolio's Terminal layout.
export function TerminalWindow({ status, children }) {
  const s = STATUS[status];
  return (
    <div className="mx-4 my-8 max-w-5xl overflow-hidden rounded-xl border border-white/10 bg-warm-ink shadow-2xl md:mx-auto md:my-12">
      <div className="flex items-center gap-2 border-b border-white/10 bg-black/30 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
        <span className="h-2.5 w-2.5 rounded-full bg-white/20" />
        <span className="h-2.5 w-2.5 rounded-full bg-gold/70" />
        <span className="ml-3 text-[11px] text-white/50">~/data-analyst-agent</span>
        <span className="ml-auto flex items-center gap-2 text-[11px] text-white/50">
          <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
          {s.label}
        </span>
      </div>
      <div className="p-6 md:p-10">{children}</div>
    </div>
  );
}

export const Prompt = ({ children, className = "" }) => (
  <p className={`text-[12px] break-words text-gold ${className}`}>
    <span className="select-none">$ </span>
    {children}
  </p>
);

export const Caret = () => <span className="caret ml-0.5 inline-block h-[1em] w-[0.55em] translate-y-[2px] bg-gold" />;

const FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏";
export function Spinner() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % FRAMES.length), 80);
    return () => clearInterval(id);
  }, []);
  return <span className="text-gold">{FRAMES[i]}</span>;
}
