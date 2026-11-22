// FASTAPI_ORIGIN is the dedicated staging service's HTTPS origin.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const allowed = ["/api/v1/videos/", "/api/v1/export/", "/results/"];
    if (url.hostname !== "staging.formrefine.ai" || !allowed.some(p => url.pathname.startsWith(p))) {
      return new Response("Not found", { status: 404 });
    }
    if (!env.FASTAPI_ORIGIN) return new Response("Staging backend unavailable", { status: 503 });
    const upstream = new URL(env.FASTAPI_ORIGIN);
    if (upstream.protocol !== "https:" || upstream.hostname === url.hostname) {
      return new Response("Invalid staging backend", { status: 503 });
    }
    upstream.pathname = url.pathname;
    upstream.search = url.search;
    const headers = new Headers();
    for (const key of ["accept", "content-type", "cookie", "origin", "range"]) {
      if (request.headers.has(key)) headers.set(key, request.headers.get(key));
    }
    const response = await fetch(upstream, {
      method: request.method, headers, body: request.body, redirect: "manual",
    });
    const output = new Response(response.body, response);
    output.headers.set("Cache-Control", "private, no-store");
    return output;
  },
};
