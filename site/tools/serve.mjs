/**
 * Serve `dist/` the way `vercel.json` says the host will.
 *
 * One definition, used by the header walk and the layout audit, because they
 * disagreed and the disagreement was invisible. The audit used `vite preview`,
 * whose SPA fallback answers *every* path with `index.html` — fine while the
 * site was one document and a client-side router, and wrong the moment each
 * route became its own prerendered file. It rendered the landing page at
 * `/docs`, the client hydrated the docs screen over it, and React reported a
 * mismatch on eight pages at four widths: 238 failures describing a defect in
 * the harness rather than in the site.
 *
 * The rules here are the host's, in the host's order: redirects, then the file
 * if there is one, then `<path>/index.html`, then `404.html` with a 404.
 */

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import { join, extname } from "node:path";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".json": "application/json",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".webmanifest": "application/manifest+json",
};

/**
 * Vercel injects the Web Analytics endpoints at the edge; they are not in
 * `dist/`.
 *
 * Without this a static server answers them with whatever its fallback is, so
 * the browser refuses an HTML document offered as a script and every page
 * reports a console error — a defect in the harness rather than in the policy.
 * Answering with the right content type and an empty body reproduces
 * production's *shape*, which is what these tools check: if `script-src` ever
 * stopped allowing `'self'`, or `connect-src` went back to `'none'`, the
 * refusal would still be a CSP refusal and would still be caught.
 */
function edgeStub(pathname) {
  if (pathname === "/_vercel/insights/script.js") return { type: "text/javascript", body: "" };
  if (pathname.startsWith("/_vercel/insights/")) return { type: "application/json", body: "{}" };
  return null;
}

export function startStaticServer({ dist = "dist", config = "vercel.json" } = {}) {
  const rules = JSON.parse(readFileSync(config, "utf8"));

  /** The headers the config declares for a path, in its own order. */
  const headersFor = (pathname) => {
    const out = {};
    for (const rule of rules.headers ?? []) {
      const pattern = new RegExp(`^${rule.source.replace(/\/\(\.\*\)$/, "/.*")}$`);
      if (pattern.test(pathname)) for (const { key, value } of rule.headers) out[key] = value;
    }
    return out;
  };

  const resolve = (pathname) => {
    const direct = join(dist, pathname);
    if (extname(direct) && existsSync(direct)) return { file: direct, served: pathname, status: 200 };

    const asDirectory = join(direct, "index.html");
    if (existsSync(asDirectory)) return { file: asDirectory, served: pathname, status: 200 };

    return { file: join(dist, "404.html"), served: pathname, status: 404 };
  };

  const server = createServer(async (req, res) => {
    const pathname = new URL(req.url, "http://x").pathname;

    const stub = edgeStub(pathname);
    if (stub) {
      res.writeHead(200, { "Content-Type": stub.type, ...headersFor(pathname) });
      res.end(stub.body);
      return;
    }

    for (const rule of rules.redirects ?? []) {
      if (!new RegExp(`^${rule.source}$`).test(pathname)) continue;
      res.writeHead(rule.permanent === false ? 307 : 308, { Location: rule.destination });
      res.end();
      return;
    }

    const { file, served, status } = resolve(pathname);
    res.writeHead(status, {
      "Content-Type": TYPES[extname(file)] ?? "application/octet-stream",
      ...headersFor(served),
    });
    res.end(await readFile(file));
  });

  return new Promise((ready) => {
    server.listen(0, () => ready({ server, base: `http://localhost:${server.address().port}` }));
  });
}
