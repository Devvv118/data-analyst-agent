import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Terminal-themed markdown (mirrors the "term" theme of the portfolio's Readme.jsx).
const components = {
  h1: ({ children }) => <h2 className="mt-6 mb-3 font-mono text-lg text-gold-soft">{children}</h2>,
  h2: ({ children }) => <h2 className="mt-6 mb-3 font-mono text-lg text-gold-soft">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-5 mb-2 font-mono text-base text-gold-soft">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-4 mb-2 font-mono text-sm text-gold-soft">{children}</h4>,
  p: ({ children }) => <p className="my-3 font-mono text-[13px] leading-relaxed text-cream/80">{children}</p>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1.5 pl-6 marker:text-gold">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1.5 pl-6 marker:text-gold">{children}</ol>,
  li: ({ children }) => <li className="font-mono text-[13px] leading-relaxed text-cream/80">{children}</li>,
  strong: ({ children }) => <strong className="font-medium text-cream">{children}</strong>,
  hr: () => <hr className="my-6 border-white/15" />,
  blockquote: ({ children }) => <blockquote className="my-4 border-l-2 border-gold pl-4 text-cream/70">{children}</blockquote>,
  a: ({ href = "", children }) =>
    /^https?:/.test(href) ? (
      <a href={href} target="_blank" rel="noreferrer" className="text-gold underline underline-offset-4 transition-colors hover:text-gold-soft">
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
  code: ({ children }) => <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.85em] text-gold-soft">{children}</code>,
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto rounded-xl bg-black/40 p-4 font-mono text-[12.5px] leading-relaxed text-cream [&_code]:bg-transparent! [&_code]:p-0! [&_code]:text-inherit!">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse font-mono text-[12.5px]">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-white/15 px-3 py-1.5 text-left font-medium text-gold-soft">{children}</th>,
  td: ({ children }) => <td className="border border-white/15 px-3 py-1.5 text-cream/75">{children}</td>,
};

export default function Markdown({ source }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {source}
    </ReactMarkdown>
  );
}
