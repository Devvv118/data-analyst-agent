export default function Notices({ status }) {
  const waking = status === "connecting";
  return (
    <div className="mt-8">
      <div className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-[13px] ${waking ? "border-notice/40 bg-notice/[0.07]" : "border-white/10 bg-white/[0.03]"}`}>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full bg-notice ${waking ? "animate-pulse" : ""}`} />
        <span className="text-cream">The server may take up to a minute to start up.</span>
      </div>
    </div>
  );
}
