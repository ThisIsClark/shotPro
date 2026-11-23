// FASTAPI_ORIGIN is the dedicated staging service's HTTPS origin.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const allowed = ["/api/v1/videos/", "/api/v1/export/", "/results/"];
    const publicPage = ["/", "/app", "/privacy", "/guides"].includes(url.pathname)
      || ["/static/", "/guides/", "/template_images/", "/api/v1/templates/"].some(p => url.pathname.startsWith(p));
    const publicRead = publicPage && ["GET", "HEAD"].includes(request.method);
    if (url.hostname !== "staging.formrefine.ai" || (!publicRead && !allowed.some(p => url.pathname.startsWith(p)))) {
      return new Response("Not found", { status: 404 });
    }
    const upstream = new URL(env.FASTAPI_ORIGIN || "https://welcoming-healing-staging.up.railway.app");
    if (upstream.protocol !== "https:" || upstream.hostname === url.hostname) {
      return new Response("Invalid staging backend", { status: 503 });
    }
    upstream.pathname = url.pathname === "/" ? "/app" : url.pathname;
    upstream.search = url.search;
    const headers = new Headers();
    for (const key of ["accept", "content-type", "cookie", "origin", "range"]) {
      if (publicRead && key === "cookie") continue;
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
