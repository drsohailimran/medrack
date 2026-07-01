import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";

// Renders backend answer text: "•" bullets, indented "–"/"—" sub-bullets,
// **bold**, "Heading:" / "## heading" section headers, and plain paragraphs.
// Tightly formatted to match the downloaded PDF. (The previous version only
// recognised hyphen "-" bullets, so en-dash "–" sub-bullets fell through to
// paragraphs and rendered with large vertical gaps — the "too spaced" look.)

type ListItem = { text: string; level: number };
type Block =
  | { kind: "heading"; level: 2 | 3; text: string }
  | { kind: "list"; items: ListItem[] }
  | { kind: "table"; rows: string[][] }
  | { kind: "diagram"; dot: string }
  | { kind: "p"; text: string };

// Bullet markers: hyphen, asterisk, bullet dots, en-dash, em-dash.
const BULLET = /^(\s*)([-*•‣⁃–—])\s+(.*)$/;
const MD_HEADING = /^\s*(#{1,6})\s+(.*)$/;
const COLON_HEADING = /^([A-Z][A-Za-z0-9 /&()-]{0,58}):\s*$/;
// A standalone section heading: short, capitalised, no bullet, no terminal
// punctuation — mirrors the PDF renderer's heading detection so the on-screen
// preview styles headings like "Definition" / "Core Components of EOC" too.
const HEADING_LINE = /^[A-Z][A-Za-z0-9 \-/&,'()–—]{1,78}$/;
function isHeadingLine(s: string): boolean {
  return HEADING_LINE.test(s) && !/[.:;,!?]$/.test(s);
}

// Markdown table detection.
function isTableSeparator(line: string): boolean {
  const s = line.trim();
  if (!s.includes("-") || !s.includes("|")) return false;
  return s
    .replace(/^\||\|$/g, "")
    .split("|")
    .every((c) => /^\s*:?-{1,}:?\s*$/.test(c));
}
function splitTableRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

function levelForIndent(indent: string): number {
  const spaces = indent.replace(/\t/g, "    ").length;
  if (spaces >= 6) return 2;
  if (spaces >= 2) return 1;
  return 0;
}

function parseBlocks(answer: string): Block[] {
  const normalized = (answer ?? "").replace(/\r\n/g, "\n");
  if (!normalized.trim()) return [];
  const lines = normalized.split("\n");
  const blocks: Block[] = [];
  let list: ListItem[] | null = null;
  let para: string[] = [];

  const flushPara = () => {
    if (para.length) {
      blocks.push({ kind: "p", text: para.join(" ") });
      para = [];
    }
  };
  const flushList = () => {
    if (list && list.length) blocks.push({ kind: "list", items: list });
    list = null;
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i].replace(/\s+$/, "");
    if (!line.trim()) {
      // A blank line ends a paragraph but NOT a list — bullets separated by
      // blank lines still belong to one continuous list.
      flushPara();
      i++;
      continue;
    }
    // Fenced Graphviz/DOT flowchart: ```dot ... ```
    if (/^\s*`{3,}\s*(dot|graphviz)\s*$/i.test(line)) {
      flushPara();
      flushList();
      const dotLines: string[] = [];
      let j = i + 1;
      while (j < lines.length && !/^\s*`{3,}\s*$/.test(lines[j])) {
        dotLines.push(lines[j]);
        j++;
      }
      blocks.push({ kind: "diagram", dot: dotLines.join("\n") });
      i = j + 1;
      continue;
    }
    // A markdown bold-only line "**Heading**" is a section heading (some
    // generations use **bold** for headings instead of plain text).
    const boldHead = /^\*\*\s*(.+?)\s*\*\*[:.]?$/.exec(line.trim());
    if (boldHead) {
      flushPara();
      flushList();
      blocks.push({ kind: "heading", level: 3, text: boldHead[1].trim() });
      i++;
      continue;
    }
    // Markdown table: a row with '|' whose next line is a separator row.
    if (line.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      flushPara();
      flushList();
      const rows: string[][] = [splitTableRow(line)];
      let j = i + 2;
      while (
        j < lines.length &&
        lines[j].trim() &&
        lines[j].includes("|") &&
        !isTableSeparator(lines[j])
      ) {
        rows.push(splitTableRow(lines[j]));
        j++;
      }
      blocks.push({ kind: "table", rows });
      i = j;
      continue;
    }
    const md = MD_HEADING.exec(line);
    const bullet = BULLET.exec(line);
    const colon = COLON_HEADING.exec(line.trim());
    if (md) {
      flushPara();
      flushList();
      blocks.push({ kind: "heading", level: md[1].length <= 2 ? 2 : 3, text: md[2].trim() });
    } else if (bullet) {
      flushPara();
      if (!list) list = [];
      list.push({ text: bullet[3].trim(), level: levelForIndent(bullet[1]) });
    } else if (colon || isHeadingLine(line.trim())) {
      flushPara();
      flushList();
      blocks.push({ kind: "heading", level: 3, text: (colon ? colon[1] : line).trim() });
    } else {
      flushList();
      para.push(line.trim());
    }
    i++;
  }
  flushPara();
  flushList();
  return blocks;
}

function renderInline(text: string, keyBase: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[chunk_[a-zA-Z0-9_]+\])/g).filter(Boolean);
  return parts.map((p, i) => {
    const key = `${keyBase}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(p)) {
      return <strong key={key}>{p.slice(2, -2)}</strong>;
    }
    if (/^\[chunk_/.test(p)) {
      return (
        <span
          key={key}
          className="ml-0.5 inline-flex items-center rounded border border-primary/30 bg-primary/10 px-1 py-px font-mono text-[10px] text-primary"
          title="Evidence reference"
        >
          {p.replace(/[[\]]/g, "")}
        </span>
      );
    }
    return <span key={key}>{p}</span>;
  });
}

export function AnswerViewer({ answer }: { answer: string }) {
  const blocks = useMemo(() => parseBlocks(answer), [answer]);

  if (!blocks.length) {
    return (
      <article className="mx-auto max-w-[80ch] px-4 py-6 font-serif sm:px-8 text-[15px]">
        <p className="whitespace-pre-wrap leading-relaxed">{answer}</p>
      </article>
    );
  }

  return (
    <article className="mx-auto max-w-[80ch] px-4 py-6 font-serif sm:px-8 text-[15px] text-foreground/90">
      {blocks.map((b, i) => {
        if (b.kind === "heading") {
          const cls =
            b.level === 2
              ? "mt-4 mb-1.5 font-display text-[13px] font-semibold uppercase tracking-wide text-primary"
              : "mt-3 mb-1 font-display text-[13.5px] font-semibold text-primary";
          return (
            <div key={i} className={cls}>
              {renderInline(b.text, `h${i}`)}
            </div>
          );
        }
        if (b.kind === "list") {
          return (
            <ul key={i} className="my-2 space-y-1">
              {b.items.map((it, j) => (
                <li
                  key={j}
                  className="flex gap-2 leading-snug"
                  style={{ marginLeft: `${it.level * 1.15}rem` }}
                >
                  <span className="mt-[0.15rem] shrink-0 select-none text-primary/70">
                    {it.level === 0 ? "•" : "–"}
                  </span>
                  <span className="min-w-0">{renderInline(it.text, `l${i}-${j}`)}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (b.kind === "table") {
          const [header, ...body] = b.rows;
          return (
            <div key={i} className="my-3 overflow-x-auto">
              <table className="w-full border-collapse text-[13px]">
                <thead>
                  <tr>
                    {header?.map((c, j) => (
                      <th
                        key={j}
                        className="border border-border bg-primary px-3 py-1.5 text-left font-semibold text-primary-foreground"
                      >
                        {renderInline(c, `th${i}-${j}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, r) => (
                    <tr key={r} className={r % 2 ? "bg-surface-2/50" : ""}>
                      {row.map((c, j) => (
                        <td key={j} className="border border-border px-3 py-1.5 align-top">
                          {renderInline(c, `td${i}-${r}-${j}`)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (b.kind === "diagram") {
          return <GraphvizImage key={i} dot={b.dot} />;
        }
        return (
          <p key={i} className="my-2 leading-relaxed">
            {renderInline(b.text, `p${i}`)}
          </p>
        );
      })}
    </article>
  );
}

// Renders a Graphviz DOT flowchart by asking the backend to turn it into a
// PNG (the `dot` tool runs server-side). Fails silently to a small note so a
// malformed diagram never breaks the answer.
function GraphvizImage({ dot }: { dot: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    let objUrl: string | null = null;
    setUrl(null);
    setFailed(false);
    api
      .renderGraphviz(dot)
      .then((blob) => {
        if (!alive) return;
        objUrl = URL.createObjectURL(blob);
        setUrl(objUrl);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [dot]);

  if (failed) {
    return (
      <div className="my-3 rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-muted-foreground">
        (flowchart could not be rendered)
      </div>
    );
  }
  if (!url) {
    return <div className="my-3 text-xs text-muted-foreground">Rendering flowchart…</div>;
  }
  return (
    <div className="my-3 flex justify-center rounded-md border border-border bg-white p-3">
      <img src={url} alt="flowchart" className="max-w-full" />
    </div>
  );
}
