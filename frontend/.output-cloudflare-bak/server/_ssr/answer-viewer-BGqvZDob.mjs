import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime } from "../_libs/react+tanstack__react-query.mjs";
import { n as api } from "./app-shell-1ZudwU0b.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/answer-viewer-BGqvZDob.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var BULLET = /^(\s*)([-*•‣⁃–—])\s+(.*)$/;
var MD_HEADING = /^\s*(#{1,6})\s+(.*)$/;
var COLON_HEADING = /^([A-Z][A-Za-z0-9 /&()-]{0,58}):\s*$/;
var HEADING_LINE = /^[A-Z][A-Za-z0-9 \-/&,'()–—]{1,78}$/;
function isHeadingLine(s) {
	return HEADING_LINE.test(s) && !/[.:;,!?]$/.test(s);
}
function isTableSeparator(line) {
	const s = line.trim();
	if (!s.includes("-") || !s.includes("|")) return false;
	return s.replace(/^\||\|$/g, "").split("|").every((c) => /^\s*:?-{1,}:?\s*$/.test(c));
}
function splitTableRow(line) {
	let s = line.trim();
	if (s.startsWith("|")) s = s.slice(1);
	if (s.endsWith("|")) s = s.slice(0, -1);
	return s.split("|").map((c) => c.trim());
}
function levelForIndent(indent) {
	const spaces = indent.replace(/\t/g, "    ").length;
	if (spaces >= 6) return 2;
	if (spaces >= 2) return 1;
	return 0;
}
function parseBlocks(answer) {
	const normalized = (answer ?? "").replace(/\r\n/g, "\n");
	if (!normalized.trim()) return [];
	const lines = normalized.split("\n");
	const blocks = [];
	let list = null;
	let para = [];
	const flushPara = () => {
		if (para.length) {
			blocks.push({
				kind: "p",
				text: para.join(" ")
			});
			para = [];
		}
	};
	const flushList = () => {
		if (list && list.length) blocks.push({
			kind: "list",
			items: list
		});
		list = null;
	};
	let i = 0;
	while (i < lines.length) {
		const line = lines[i].replace(/\s+$/, "");
		if (!line.trim()) {
			flushPara();
			i++;
			continue;
		}
		if (/^\s*`{3,}\s*(dot|graphviz)\s*$/i.test(line)) {
			flushPara();
			flushList();
			const dotLines = [];
			let j = i + 1;
			while (j < lines.length && !/^\s*`{3,}\s*$/.test(lines[j])) {
				dotLines.push(lines[j]);
				j++;
			}
			blocks.push({
				kind: "diagram",
				dot: dotLines.join("\n")
			});
			i = j + 1;
			continue;
		}
		const boldHead = /^\*\*\s*(.+?)\s*\*\*[:.]?$/.exec(line.trim());
		if (boldHead) {
			flushPara();
			flushList();
			blocks.push({
				kind: "heading",
				level: 3,
				text: boldHead[1].trim()
			});
			i++;
			continue;
		}
		if (line.includes("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
			flushPara();
			flushList();
			const rows = [splitTableRow(line)];
			let j = i + 2;
			while (j < lines.length && lines[j].trim() && lines[j].includes("|") && !isTableSeparator(lines[j])) {
				rows.push(splitTableRow(lines[j]));
				j++;
			}
			blocks.push({
				kind: "table",
				rows
			});
			i = j;
			continue;
		}
		const md = MD_HEADING.exec(line);
		const bullet = BULLET.exec(line);
		const colon = COLON_HEADING.exec(line.trim());
		if (md) {
			flushPara();
			flushList();
			blocks.push({
				kind: "heading",
				level: md[1].length <= 2 ? 2 : 3,
				text: md[2].trim()
			});
		} else if (bullet) {
			flushPara();
			if (!list) list = [];
			list.push({
				text: bullet[3].trim(),
				level: levelForIndent(bullet[1])
			});
		} else if (colon || isHeadingLine(line.trim())) {
			flushPara();
			flushList();
			blocks.push({
				kind: "heading",
				level: 3,
				text: (colon ? colon[1] : line).trim()
			});
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
function renderInline(text, keyBase) {
	return text.split(/(\*\*[^*]+\*\*|\[chunk_[a-zA-Z0-9_]+\])/g).filter(Boolean).map((p, i) => {
		const key = `${keyBase}-${i}`;
		if (/^\*\*[^*]+\*\*$/.test(p)) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("strong", { children: p.slice(2, -2) }, key);
		if (/^\[chunk_/.test(p)) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "ml-0.5 inline-flex items-center rounded border border-primary/30 bg-primary/10 px-1 py-px font-mono text-[10px] text-primary",
			title: "Evidence reference",
			children: p.replace(/[[\]]/g, "")
		}, key);
		return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: p }, key);
	});
}
function AnswerViewer({ answer }) {
	const blocks = (0, import_react.useMemo)(() => parseBlocks(answer), [answer]);
	if (!blocks.length) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("article", {
		className: "mx-auto max-w-[80ch] px-4 py-6 font-serif sm:px-8 text-[15px]",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
			className: "whitespace-pre-wrap leading-relaxed",
			children: answer
		})
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("article", {
		className: "mx-auto max-w-[80ch] px-4 py-6 font-serif sm:px-8 text-[15px] text-foreground/90",
		children: blocks.map((b, i) => {
			if (b.kind === "heading") return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: b.level === 2 ? "mt-4 mb-1.5 font-display text-[13px] font-semibold uppercase tracking-wide text-primary" : "mt-3 mb-1 font-display text-[13.5px] font-semibold text-primary",
				children: renderInline(b.text, `h${i}`)
			}, i);
			if (b.kind === "list") return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("ul", {
				className: "my-2 space-y-1",
				children: b.items.map((it, j) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
					className: "flex gap-2 leading-snug",
					style: { marginLeft: `${it.level * 1.15}rem` },
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "mt-[0.15rem] shrink-0 select-none text-primary/70",
						children: it.level === 0 ? "•" : "–"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "min-w-0",
						children: renderInline(it.text, `l${i}-${j}`)
					})]
				}, j))
			}, i);
			if (b.kind === "table") {
				const [header, ...body] = b.rows;
				return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "my-3 overflow-x-auto",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("table", {
						className: "w-full border-collapse text-[13px]",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("thead", { children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tr", { children: header?.map((c, j) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
							className: "border border-border bg-primary px-3 py-1.5 text-left font-semibold text-primary-foreground",
							children: renderInline(c, `th${i}-${j}`)
						}, j)) }) }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tbody", { children: body.map((row, r) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tr", {
							className: r % 2 ? "bg-surface-2/50" : "",
							children: row.map((c, j) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "border border-border px-3 py-1.5 align-top",
								children: renderInline(c, `td${i}-${r}-${j}`)
							}, j))
						}, r)) })]
					})
				}, i);
			}
			if (b.kind === "diagram") return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(GraphvizImage, { dot: b.dot }, i);
			return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "my-2 leading-relaxed",
				children: renderInline(b.text, `p${i}`)
			}, i);
		})
	});
}
function GraphvizImage({ dot }) {
	const [url, setUrl] = (0, import_react.useState)(null);
	const [failed, setFailed] = (0, import_react.useState)(false);
	(0, import_react.useEffect)(() => {
		let alive = true;
		let objUrl = null;
		setUrl(null);
		setFailed(false);
		api.renderGraphviz(dot).then((blob) => {
			if (!alive) return;
			objUrl = URL.createObjectURL(blob);
			setUrl(objUrl);
		}).catch(() => {
			if (alive) setFailed(true);
		});
		return () => {
			alive = false;
			if (objUrl) URL.revokeObjectURL(objUrl);
		};
	}, [dot]);
	if (failed) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "my-3 rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-muted-foreground",
		children: "(flowchart could not be rendered)"
	});
	if (!url) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "my-3 text-xs text-muted-foreground",
		children: "Rendering flowchart…"
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "my-3 flex justify-center rounded-md border border-border bg-white p-3",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("img", {
			src: url,
			alt: "flowchart",
			className: "max-w-full"
		})
	});
}
//#endregion
export { AnswerViewer as t };
