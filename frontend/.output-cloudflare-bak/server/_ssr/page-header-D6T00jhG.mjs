import { a as require_jsx_runtime } from "../_libs/react+tanstack__react-query.mjs";
import { r as cn } from "./app-shell-1ZudwU0b.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/page-header-D6T00jhG.js
var import_jsx_runtime = require_jsx_runtime();
function PageHeader({ eyebrow, title, description, actions, className }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: cn("flex flex-col gap-3 border-b border-border px-6 py-5 sm:flex-row sm:items-end sm:justify-between sm:gap-6", className),
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "min-w-0",
			children: [
				eyebrow && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "mb-1 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground",
					children: eyebrow
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
					className: "truncate font-display text-[22px] font-semibold tracking-tight text-foreground",
					children: title
				}),
				description && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-1 max-w-3xl text-sm text-muted-foreground",
					children: description
				})
			]
		}), actions && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "flex flex-wrap items-center gap-2",
			children: actions
		})]
	});
}
//#endregion
export { PageHeader as t };
