globalThis.__nitro_main__ = import.meta.url;
import { a as FastResponse, n as HTTPError, r as defineLazyEventHandler, t as H3Core } from "./_libs/h3+rou3+srvx.mjs";
import { t as HookableCore } from "./_libs/hookable.mjs";
//#region #nitro-vite-setup
function lazyService(loader) {
	let promise, mod;
	return { fetch(req) {
		if (mod) return mod.fetch(req);
		if (!promise) promise = loader().then((_mod) => mod = _mod.default || _mod);
		return promise.then((mod) => mod.fetch(req));
	} };
}
var services = { ["ssr"]: lazyService(() => import("./_ssr/ssr.mjs")) };
globalThis.__nitro_vite_envs__ = services;
//#endregion
//#region #nitro/virtual/public-assets-data
var public_assets_data_default = {
	"/assets/answer-viewer-_9fEjEml.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"12da-4RHkwrOk9zanZMFrcBpF6PTxXTk\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 4826,
		"path": "../public/assets/answer-viewer-_9fEjEml.js"
	},
	"/assets/answers-C1KwwByj.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"1a73-raYcESctBOmEq7zHqU38cceeh6I\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 6771,
		"path": "../public/assets/answers-C1KwwByj.js"
	},
	"/assets/app-shell-C_C56n4t.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"1057b-EMTvimWq8z+zy+GClsDKuvF0qCc\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 66939,
		"path": "../public/assets/app-shell-C_C56n4t.js"
	},
	"/assets/benchmarks-BhXt5IAd.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"1950-T/p7wujWxf1bjSV24LLw7R2oPCU\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 6480,
		"path": "../public/assets/benchmarks-BhXt5IAd.js"
	},
	"/assets/books-D3rMB0B5.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"22be-X2G3bLXfgweMN6C6mbAvcBhWn1M\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 8894,
		"path": "../public/assets/books-D3rMB0B5.js"
	},
	"/assets/button-BWVS6sM2.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"ff6-siqkIXBUc1P6Xx2hLM403WgskSg\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 4086,
		"path": "../public/assets/button-BWVS6sM2.js"
	},
	"/assets/chevron-right-Bakfmv7f.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"c6-nMJW8ym+GK5Xi8lks/GzSlnRy/8\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 198,
		"path": "../public/assets/chevron-right-Bakfmv7f.js"
	},
	"/assets/download-DjR0ShEF.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"e1-5t/r9yZSdHBasOHsh9GIwwg5xAY\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 225,
		"path": "../public/assets/download-DjR0ShEF.js"
	},
	"/assets/format-OMX0R9Fg.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"174-Uaqa74UzT/Wqp8LRYEm/+mYE/tc\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 372,
		"path": "../public/assets/format-OMX0R9Fg.js"
	},
	"/assets/history-Bz6vFuUK.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"18ec-1Vy1YhHQBpMTwaUuK7Ji83mmJWY\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 6380,
		"path": "../public/assets/history-Bz6vFuUK.js"
	},
	"/assets/index-BPjTG7ct.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"54d84-S9mVJa/1dxWCrXM0HyHzEjeVZto\"",
		"mtime": "2026-07-09T15:48:01.505Z",
		"size": 347524,
		"path": "../public/assets/index-BPjTG7ct.js"
	},
	"/assets/logs-DyhGpBdy.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"929-OkpnbHy7dxwio0rXeuxHdiZILFc\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 2345,
		"path": "../public/assets/logs-DyhGpBdy.js"
	},
	"/assets/page-header-DSu7ofNG.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"31f-lLULcXobZ2mFR+3ELbhYw6ZnrC4\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 799,
		"path": "../public/assets/page-header-DSu7ofNG.js"
	},
	"/assets/pipeline-zbQrvAcb.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"20e1-IVtROyOYAgWItrQxrS+bJgBuCGs\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 8417,
		"path": "../public/assets/pipeline-zbQrvAcb.js"
	},
	"/assets/play-BW9CDKFO.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"b7-fqbU5xMqjpeno/nr1Ki5x8BRa1U\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 183,
		"path": "../public/assets/play-BW9CDKFO.js"
	},
	"/assets/plus-ocBwctsF.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"92-HHJXne7p/EtwRmNEc87pqInkpX4\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 146,
		"path": "../public/assets/plus-ocBwctsF.js"
	},
	"/assets/projects-hpXCgKik.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"134b-3N4IELqHmQxX1m3j+XVkWYyxj9g\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 4939,
		"path": "../public/assets/projects-hpXCgKik.js"
	},
	"/assets/question-banks-Cerd780f.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"2b6d-lthYccpoB98HFd2dLeMVmR+xZ5Q\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 11117,
		"path": "../public/assets/question-banks-Cerd780f.js"
	},
	"/assets/refresh-cw-9jjqbx6w.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"13a-oZPr4HuhHKI59dy3sLaf8GzQZrE\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 314,
		"path": "../public/assets/refresh-cw-9jjqbx6w.js"
	},
	"/assets/routes-MJPwVD9U.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"3bf9-WY1lREZP19G8LKdAitNGn0x3G48\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 15353,
		"path": "../public/assets/routes-MJPwVD9U.js"
	},
	"/assets/settings-BODf1AnR.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"be2-DtWEHk7x71E4BMRkG6oXcBgkgOY\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 3042,
		"path": "../public/assets/settings-BODf1AnR.js"
	},
	"/assets/status-badge-DnPDfSdg.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"258-WlKE+zSJiWNU0NtpDfQOtMiE7cQ\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 600,
		"path": "../public/assets/status-badge-DnPDfSdg.js"
	},
	"/assets/styles-VTX4CDNq.css": {
		"type": "text/css; charset=utf-8",
		"etag": "\"16d05-PrlPQOrI7ZLYoz6X4TcWB+9ME+g\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 93445,
		"path": "../public/assets/styles-VTX4CDNq.css"
	},
	"/assets/trash-2-B1fjrlX9.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"141-dMMWlcT4Uv2gNdQ9lWOmSfib+hs\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 321,
		"path": "../public/assets/trash-2-B1fjrlX9.js"
	},
	"/assets/use-job-CcSxEyUW.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"7c1-NK5nUWM3lHENVISiiRAufCDMgmI\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 1985,
		"path": "../public/assets/use-job-CcSxEyUW.js"
	},
	"/assets/useMutation-DRzJjJgw.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"8a3-CSyNq21SLrJgkYcJWkKWifUX9as\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 2211,
		"path": "../public/assets/useMutation-DRzJjJgw.js"
	},
	"/assets/x-tnPibXKZ.js": {
		"type": "text/javascript; charset=utf-8",
		"etag": "\"15e-EoXX+rHEDKO5yhfJh60bCbd0nFA\"",
		"mtime": "2026-07-09T15:48:01.507Z",
		"size": 350,
		"path": "../public/assets/x-tnPibXKZ.js"
	}
};
//#endregion
//#region #nitro/virtual/public-assets
var publicAssetBases = {};
function isPublicAssetURL(id = "") {
	if (public_assets_data_default[id]) return true;
	for (const base in publicAssetBases) if (id.startsWith(base)) return true;
	return false;
}
//#endregion
//#region node_modules/nitro/dist/runtime/internal/route-rules.mjs
var headers = ((m) => function headersRouteRule(event) {
	for (const [key, value] of Object.entries(m.options || {})) event.res.headers.set(key, value);
});
//#endregion
//#region #nitro/virtual/routing
var findRouteRules = /* @__PURE__ */ (() => {
	const $0 = [{
		name: "headers",
		route: "/assets/**",
		handler: headers,
		options: { "cache-control": "public, max-age=31536000, immutable" }
	}];
	return (m, p) => {
		let r = [];
		if (p.charCodeAt(p.length - 1) === 47) p = p.slice(0, -1) || "/";
		let s = p.split("/");
		if (s.length > 1) {
			if (s[1] === "assets") r.unshift({
				data: $0,
				params: { "_": s.slice(2).join("/") }
			});
		}
		return r;
	};
})();
var _lazy_8MqYaS = defineLazyEventHandler(() => import("./_chunks/ssr-renderer.mjs"));
var findRoute = /* @__PURE__ */ (() => {
	const data = {
		route: "/**",
		handler: _lazy_8MqYaS
	};
	return ((_m, p) => {
		return {
			data,
			params: { "_": p.slice(1) }
		};
	});
})();
[].filter(Boolean);
//#endregion
//#region node_modules/nitro/dist/runtime/internal/error/prod.mjs
var errorHandler = (error, event) => {
	const res = defaultHandler(error, event);
	return new FastResponse(typeof res.body === "string" ? res.body : JSON.stringify(res.body, null, 2), res);
};
function defaultHandler(error, event) {
	const unhandled = error.unhandled ?? !HTTPError.isError(error);
	const { status = 500, statusText = "" } = unhandled ? {} : error;
	if (status === 404) {
		const url = event.url || new URL(event.req.url);
		const baseURL = "/";
		if (/^\/[^/]/.test(baseURL) && !url.pathname.startsWith(baseURL)) return {
			status: 302,
			headers: new Headers({ location: `${baseURL}${url.pathname.slice(1)}${url.search}` })
		};
	}
	const headers = new Headers(unhandled ? {} : error.headers);
	headers.set("content-type", "application/json; charset=utf-8");
	return {
		status,
		statusText,
		headers,
		body: {
			error: true,
			...unhandled ? {
				status,
				unhandled: true
			} : typeof error.toJSON === "function" ? error.toJSON() : {
				status,
				statusText,
				message: error.message
			}
		}
	};
}
//#endregion
//#region #nitro/virtual/error-handler
var errorHandlers = [errorHandler];
async function error_handler_default(error, event) {
	for (const handler of errorHandlers) try {
		const response = await handler(error, event, { defaultHandler });
		if (response) return response;
	} catch (error) {
		console.error(error);
	}
}
//#endregion
//#region #nitro/virtual/app
function createNitroApp() {
	const captureError = (error, errorCtx) => {
		if (errorCtx?.event) {
			const errors = errorCtx.event.req.context?.nitro?.errors;
			if (errors) errors.push({
				error,
				context: errorCtx
			});
		}
	};
	const h3App = createH3App({ onError(error, event) {
		return error_handler_default(error, event);
	} });
	let appHandler = (req) => {
		req.context ||= {};
		req.context.nitro = req.context.nitro || { errors: [] };
		return h3App.fetch(req);
	};
	return {
		fetch: appHandler,
		h3: h3App,
		hooks: void 0,
		captureError
	};
}
function createH3App(config) {
	const h3App = new H3Core(config);
	h3App["~findRoute"] = (event) => findRoute(event.req.method, event.url.pathname);
	h3App["~getMiddleware"] = (event, route) => {
		const pathname = event.url.pathname;
		const method = event.req.method;
		const middleware = [];
		const routeRules = getRouteRules(method, pathname);
		event.context.routeRules = routeRules?.routeRules;
		if (routeRules?.routeRuleMiddleware.length) middleware.push(...routeRules.routeRuleMiddleware);
		if (route?.data?.middleware?.length) middleware.push(...route.data.middleware);
		return middleware;
	};
	return h3App;
}
//#endregion
//#region node_modules/nitro/dist/runtime/internal/app.mjs
var APP_ID = "default";
function useNitroApp() {
	let instance = useNitroApp._instance;
	if (instance) return instance;
	instance = useNitroApp._instance = createNitroApp();
	globalThis.__nitro__ = globalThis.__nitro__ || {};
	globalThis.__nitro__[APP_ID] = instance;
	return instance;
}
function useNitroHooks() {
	const nitroApp = useNitroApp();
	const hooks = nitroApp.hooks;
	if (hooks) return hooks;
	return nitroApp.hooks = new HookableCore();
}
function getRouteRules(method, pathname) {
	const m = findRouteRules(method, pathname);
	if (!m?.length) return { routeRuleMiddleware: [] };
	const routeRules = {};
	for (const layer of m) for (const rule of layer.data) {
		const currentRule = routeRules[rule.name];
		if (currentRule) {
			if (rule.options === false) {
				delete routeRules[rule.name];
				continue;
			}
			if (typeof currentRule.options === "object" && typeof rule.options === "object") currentRule.options = {
				...currentRule.options,
				...rule.options
			};
			else currentRule.options = rule.options;
			currentRule.route = rule.route;
			currentRule.params = {
				...currentRule.params,
				...layer.params
			};
		} else if (rule.options !== false) routeRules[rule.name] = {
			...rule,
			params: layer.params
		};
	}
	const middleware = [];
	const orderedRules = Object.values(routeRules).sort((a, b) => (a.handler?.order || 0) - (b.handler?.order || 0));
	for (const rule of orderedRules) {
		if (rule.options === false || !rule.handler) continue;
		middleware.push(rule.handler(rule));
	}
	return {
		routeRules,
		routeRuleMiddleware: middleware
	};
}
//#endregion
//#region node_modules/nitro/dist/presets/cloudflare/runtime/_module-handler.mjs
function createHandler(hooks) {
	const nitroApp = useNitroApp();
	const nitroHooks = useNitroHooks();
	return {
		async fetch(request, env, context) {
			globalThis.__env__ = env;
			augmentReq(request, {
				env,
				context
			});
			const ctxExt = {};
			const url = new URL(request.url);
			if (hooks.fetch) {
				const res = await hooks.fetch(request, env, context, url, ctxExt);
				if (res) return res;
			}
			return await nitroApp.fetch(request);
		},
		scheduled(controller, env, context) {
			globalThis.__env__ = env;
			context.waitUntil(nitroHooks.callHook("cloudflare:scheduled", {
				controller,
				env,
				context
			}) || Promise.resolve());
		},
		email(message, env, context) {
			globalThis.__env__ = env;
			context.waitUntil(nitroHooks.callHook("cloudflare:email", {
				message,
				event: message,
				env,
				context
			}) || Promise.resolve());
		},
		queue(batch, env, context) {
			globalThis.__env__ = env;
			context.waitUntil(nitroHooks.callHook("cloudflare:queue", {
				batch,
				event: batch,
				env,
				context
			}) || Promise.resolve());
		},
		tail(traces, env, context) {
			globalThis.__env__ = env;
			context.waitUntil(nitroHooks.callHook("cloudflare:tail", {
				traces,
				env,
				context
			}) || Promise.resolve());
		},
		trace(traces, env, context) {
			globalThis.__env__ = env;
			context.waitUntil(nitroHooks.callHook("cloudflare:trace", {
				traces,
				env,
				context
			}) || Promise.resolve());
		}
	};
}
function augmentReq(cfReq, ctx) {
	const req = cfReq;
	req.ip = cfReq.headers.get("cf-connecting-ip") || void 0;
	req.runtime ??= { name: "cloudflare" };
	req.runtime.cloudflare = {
		...req.runtime.cloudflare,
		...ctx
	};
	req.waitUntil = ctx.context?.waitUntil.bind(ctx.context);
}
//#endregion
//#region node_modules/nitro/dist/presets/cloudflare/runtime/cloudflare-module.mjs
var cloudflare_module_default = createHandler({ fetch(cfRequest, env, context, url) {
	if (env.ASSETS && isPublicAssetURL(url.pathname)) return env.ASSETS.fetch(cfRequest);
} });
//#endregion
export { cloudflare_module_default as default };
