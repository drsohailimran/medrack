//#region node_modules/.nitro/vite/services/ssr/assets/format-BX-FBxQr.js
/**
* Parse a timestamp that may be in either:
*  - ISO 8601 extended: "2026-06-29T20:02:21Z" (JavaScript native)
*  - ISO 8601 basic:   "20260629T200221Z" (used by backend benchmark reports)
*  - Anything `new Date()` would accept directly.
* Returns a valid Date or null on failure.
*/
function parseTimestamp(input) {
	if (!input) return null;
	const direct = new Date(input);
	if (!isNaN(direct.getTime())) return direct;
	const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(input);
	if (m) return /* @__PURE__ */ new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`);
	return null;
}
/** Format a timestamp for display, returning a placeholder if unparseable. */
function formatTimestamp(input, fallback = "—") {
	const d = parseTimestamp(input);
	if (!d) return fallback;
	return d.toLocaleString();
}
/** Format a date only (no time), returning a placeholder if unparseable. */
function formatDate(input, fallback = "—") {
	const d = parseTimestamp(input);
	if (!d) return fallback;
	return d.toLocaleDateString();
}
//#endregion
export { formatTimestamp as n, formatDate as t };
