import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime } from "../_libs/react+tanstack__react-query.mjs";
import { n as api, r as cn } from "./app-shell-1ZudwU0b.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/use-job-DrhZwuCz.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function ProgressBar({ percent, label, error, className }) {
	const p = Math.max(0, Math.min(100, Number.isFinite(percent) ? percent : 0));
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: cn("w-full", className),
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "mb-1 flex items-center justify-between gap-2 text-[11px]",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "truncate text-muted-foreground",
					children: label
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
					className: cn("font-mono tabular-nums", error ? "text-destructive" : "text-foreground"),
					children: [p.toFixed(2), "%"]
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "h-2 w-full overflow-hidden rounded-full bg-muted",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: cn("h-full rounded-full transition-[width] duration-300", error ? "bg-destructive" : "bg-primary"),
					style: { width: `${p}%` }
				})
			}),
			error ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
				className: "mt-1 text-[11px] text-destructive",
				children: error
			}) : null
		]
	});
}
function useJob(storageKey) {
	const [job, setJob] = (0, import_react.useState)(null);
	const timer = (0, import_react.useRef)(null);
	const stop = (0, import_react.useCallback)(() => {
		if (timer.current) {
			clearInterval(timer.current);
			timer.current = null;
		}
	}, []);
	const clearStorage = (0, import_react.useCallback)(() => {
		if (storageKey) try {
			localStorage.removeItem(storageKey);
		} catch {}
	}, [storageKey]);
	const reset = (0, import_react.useCallback)(() => {
		stop();
		clearStorage();
		setJob(null);
	}, [stop, clearStorage]);
	const poll = (0, import_react.useCallback)((jobId, isResume) => {
		stop();
		let misses = 0;
		let settledOnce = false;
		const tick = async () => {
			try {
				const s = await api.getJob(jobId);
				misses = 0;
				settledOnce = true;
				setJob(s);
				if (s.status === "done" || s.status === "error") stop();
			} catch {
				if (isResume && !settledOnce) {
					stop();
					clearStorage();
					setJob(null);
					return;
				}
				misses += 1;
				if (misses >= 6) {
					stop();
					setJob((cur) => cur ? {
						...cur,
						status: "error",
						error: "Lost connection to the server."
					} : cur);
				}
			}
		};
		tick();
		timer.current = setInterval(tick, 800);
	}, [stop, clearStorage]);
	const start = (0, import_react.useCallback)((jobId) => {
		if (storageKey) try {
			localStorage.setItem(storageKey, jobId);
		} catch {}
		setJob({
			schema_version: 1,
			job_id: jobId,
			kind: "",
			status: "pending",
			percent: 0,
			message: "Starting…",
			result: null,
			error: null
		});
		poll(jobId, false);
	}, [poll, storageKey]);
	(0, import_react.useEffect)(() => {
		if (!storageKey) return;
		let saved = null;
		try {
			saved = localStorage.getItem(storageKey);
		} catch {}
		if (saved) {
			setJob({
				schema_version: 1,
				job_id: saved,
				kind: "",
				status: "pending",
				percent: 0,
				message: "Reconnecting…",
				result: null,
				error: null
			});
			poll(saved, true);
		}
	}, [storageKey]);
	(0, import_react.useEffect)(() => () => stop(), [stop]);
	return {
		job,
		start,
		stop,
		reset
	};
}
//#endregion
export { useJob as n, ProgressBar as t };
