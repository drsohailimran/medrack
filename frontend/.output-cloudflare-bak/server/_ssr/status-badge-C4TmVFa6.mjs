import { a as require_jsx_runtime } from "../_libs/react+tanstack__react-query.mjs";
import { r as cn } from "./app-shell-1ZudwU0b.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/status-badge-C4TmVFa6.js
var import_jsx_runtime = require_jsx_runtime();
var VARIANTS = {
	pass: "bg-success/15 text-success ring-success/30",
	warn: "bg-warning/15 text-warning ring-warning/30",
	fail: "bg-destructive/15 text-destructive ring-destructive/30",
	info: "bg-muted text-muted-foreground ring-border",
	primary: "bg-primary/15 text-primary ring-primary/30"
};
function StatusBadge({ tone = "info", children, className }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
		className: cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", VARIANTS[tone in VARIANTS ? tone : "info"], className),
		children
	});
}
//#endregion
export { StatusBadge as t };
