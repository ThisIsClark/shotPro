// Cloudflare forwards the app to FastAPI. GeFeiSites remains the login issuer.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const publicHost = env.PUBLIC_HOST || "staging.formrefine.ai";
    if (url.hostname !== publicHost) {
      return new Response("Not found", { status: 404 });
    }

    const engineAuth = ["/_auth/me", "/_auth/google/start", "/_auth/google/callback", "/_auth/logout"];
    if (engineAuth.includes(url.pathname)) {
      if (env.ENGINE) return env.ENGINE.fetch(request);
      if (env.USE_ENGINE_ORIGIN === "true") return fetch(request);
    }

    const publicPage = ["/", "/app", "/privacy", "/guides", "/health", "/robots.txt", "/sitemap.xml"].includes(url.pathname)
      || ["/static/", "/guides/", "/template_images/", "/api/v1/templates/"].some(path => url.pathname.startsWith(path));
    const publicRead = publicPage && ["GET", "HEAD"].includes(request.method);
    const adminPath = env.ADMIN_ENABLED === "true" &&
      ((url.pathname === "/admin" && ["GET", "HEAD"].includes(request.method)) ||
       url.pathname.startsWith("/api/v1/admin/"));
    const analytics = request.method === "POST" && ["/api/v1/audit/visit", "/api/v1/audit/journey"].includes(url.pathname);
    const privatePath = adminPath || analytics || ["/api/v1/videos/", "/api/v1/export/", "/results/"].some(path => url.pathname.startsWith(path));
    if (!publicRead && !privatePath) {
      return new Response("Not found", { status: 404 });
    }
    if (!env.FASTAPI_ORIGIN) {
      return new Response("Analysis service unavailable", { status: 503 });
    }

    let upstream;
    try {
      upstream = new URL(env.FASTAPI_ORIGIN);
      if (upstream.protocol !== "https:" || upstream.hostname === publicHost ||
          upstream.username || upstream.password || upstream.pathname !== "/" ||
          upstream.search || upstream.hash) {
        throw new Error("Invalid FastAPI origin");
      }
    } catch {
      return new Response("Analysis service unavailable", { status: 503 });
    }

    upstream.pathname = url.pathname;
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
    if (publicRead && response.ok && env.INDEX_PUBLIC_PAGES === "true" &&
        output.headers.get("X-FormRefine-Indexable") === "1") {
      output.headers.delete("X-Robots-Tag");
    }
    output.headers.delete("X-FormRefine-Indexable");
    output.headers.set("Cache-Control", "private, no-store");
    return output;
  },
};
