/**
 * Cloudflare Worker — anonymous launch counter for Valo Optimise.
 *
 * Deploy: wrangler deploy workers/launch-counter.js --name valo-launch-counter
 *
 * Uses Cloudflare KV namespace "LAUNCH_COUNTS" for persistence.
 *
 * Endpoints:
 *   POST /ping?v=2.0.0          — increment counter (called by app on launch)
 *   GET  /stats                  — return JSON counts (for you to check)
 *
 * No personal data stored. Only counts version strings.
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS headers
    const headers = {
      "Access-Control-Allow-Origin": "*",
      "Content-Type": "application/json",
    };

    // POST /ping?v=2.0.0 — app calls this on launch
    if (request.method === "POST" && url.pathname === "/ping") {
      const version = url.searchParams.get("v") || "unknown";
      const key = `launches:${version}`;
      const totalKey = "launches:total";

      const current = parseInt(await env.LAUNCH_COUNTS.get(key) || "0");
      const total = parseInt(await env.LAUNCH_COUNTS.get(totalKey) || "0");

      await env.LAUNCH_COUNTS.put(key, String(current + 1));
      await env.LAUNCH_COUNTS.put(totalKey, String(total + 1));

      return new Response(JSON.stringify({ ok: true }), { headers });
    }

    // GET /stats — check counts
    if (request.method === "GET" && url.pathname === "/stats") {
      const keys = await env.LAUNCH_COUNTS.list();
      const stats = {};
      for (const key of keys.keys) {
        stats[key.name] = parseInt(await env.LAUNCH_COUNTS.get(key.name) || "0");
      }
      return new Response(JSON.stringify(stats, null, 2), { headers });
    }

    return new Response(JSON.stringify({ error: "not found" }), { status: 404, headers });
  },
};
