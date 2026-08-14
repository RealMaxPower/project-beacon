/**
 * Write a real document for every route, with its content already in it.
 *
 * The site was a single empty `<div id="root">` and four fragment routes. A
 * crawler that runs no JavaScript — which is most of the ones that feed answer
 * engines — received zero words. A crawler that does run it received one URL,
 * because a fragment is never sent to a server, so `/#/docs` and `/` are the
 * same address as far as anything indexing is concerned.
 *
 * This renders each page to static markup, injects it into the built shell
 * with that page's own title, description, canonical and structured data, and
 * writes it to the path it is served at. `sitemap.xml` and `robots.txt` come
 * from the same table, so a page cannot exist in one and be missing from the
 * others.
 *
 *     npm run prerender          (runs as part of `npm run build`)
 *
 * Ordering matters: this reads `dist/index.html`, which the client build
 * produces, so it has to run after it and before anything that serves `dist`.
 */

import { renderToString } from "react-dom/server";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { SiteB } from "@b/SiteB";
import { PAGES, SITE_ORIGIN, SITE_NAME, FAQ, type Page } from "@b/pages";
import { scenarios } from "@/data/fixtures";
import { scenarioCopy } from "@/data/copy";
import { toMarkdown } from "./to-markdown";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(ROOT, "dist");
const REPO = "https://github.com/RealMaxPower/project-beacon";

const shell = readFileSync(join(DIST, "index.html"), "utf8");

function escapeAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Render one page as the server sees it.
 *
 * `window` does not exist here, so `useBRoute` reads the path from a global
 * this sets. `useTheme` falls back to dark for the same reason — which is why
 * the stylesheet, not a script, decides the first paint: see the
 * `prefers-color-scheme` block in `tokens-b.css`.
 */
function render(page: Page): string {
  (globalThis as { __BEACON_PRERENDER_PATH__?: string }).__BEACON_PRERENDER_PATH__ = page.path;
  return renderToString(<SiteB />);
}

/**
 * The structured data, as one graph rather than four loose blocks.
 *
 * `@id` references let the software, the site and the organisation point at
 * each other instead of each restating the others' fields, which is the form a
 * consumer can resolve rather than guess at.
 *
 * `FAQPage` goes on the page that renders the questions and nowhere else.
 * Attaching it to `/docs` as well would put the same markup on two URLs and
 * describe one of them wrongly, which is how a rich result gets dropped rather
 * than duplicated.
 */
function structuredData(page: Page): string {
  const graph: Record<string, unknown>[] = [
    {
      "@type": "WebSite",
      "@id": `${SITE_ORIGIN}/#website`,
      url: `${SITE_ORIGIN}/`,
      name: SITE_NAME,
      description: PAGES[0].description,
      inLanguage: "en",
      publisher: { "@id": `${SITE_ORIGIN}/#org` },
    },
    {
      "@type": "Organization",
      "@id": `${SITE_ORIGIN}/#org`,
      name: SITE_NAME,
      url: `${SITE_ORIGIN}/`,
      logo: `${SITE_ORIGIN}/mark.svg`,
      sameAs: [REPO],
    },
    {
      "@type": "SoftwareSourceCode",
      "@id": `${SITE_ORIGIN}/#software`,
      name: SITE_NAME,
      description: PAGES[0].description,
      url: `${SITE_ORIGIN}/`,
      codeRepository: REPO,
      programmingLanguage: "Python",
      runtimePlatform: "Python 3.11+",
      license: "https://www.apache.org/licenses/LICENSE-2.0",
      author: { "@id": `${SITE_ORIGIN}/#org` },
      applicationCategory: "DeveloperApplication",
      operatingSystem: "Linux, macOS, Windows",
      keywords: [
        "AI agent evaluation",
        "agent testing",
        "evidence bundle",
        "Model Context Protocol",
        "MCP",
        "A2A",
        "deterministic grading",
        "agent observability",
      ].join(", "),
    },
    {
      "@type": "WebPage",
      "@id": `${SITE_ORIGIN}${page.path}#page`,
      url: `${SITE_ORIGIN}${page.path}`,
      name: page.title,
      description: page.description,
      isPartOf: { "@id": `${SITE_ORIGIN}/#website` },
      about: { "@id": `${SITE_ORIGIN}/#software` },
      inLanguage: "en",
    },
  ];

  if (page.route === "") {
    graph.push({
      "@type": "FAQPage",
      "@id": `${SITE_ORIGIN}/#faq`,
      mainEntity: FAQ.map(({ q, a }) => ({
        "@type": "Question",
        name: q,
        acceptedAnswer: { "@type": "Answer", text: a },
      })),
    });
  } else {
    graph.push({
      "@type": "BreadcrumbList",
      "@id": `${SITE_ORIGIN}${page.path}#breadcrumb`,
      itemListElement: [
        { "@type": "ListItem", position: 1, name: SITE_NAME, item: `${SITE_ORIGIN}/` },
        { "@type": "ListItem", position: 2, name: page.title.split(" — ")[0].split(" | ")[0] },
      ],
    });
  }

  // `</` inside a script element ends it, whatever the JSON says.
  return JSON.stringify({ "@context": "https://schema.org", "@graph": graph }).replace(
    /<\//g,
    "<\\/",
  );
}

/*
 * Lift inline styles out of the markup and into a real stylesheet.
 *
 * `style-src 'self'` forbids `style` attributes, and until now the site had
 * none: React writes styles through the CSSOM, which CSP does not govern, so
 * the policy was strict in a way nothing was testing. Prerendering turns those
 * same styles into attributes in the served HTML, and the header walk failed
 * on every page carrying one — correctly, and on the first run.
 *
 * The choice was to relax the policy or to stop emitting the attributes. This
 * is the second: each distinct declaration becomes a rule keyed by a data
 * attribute, which is a stylesheet from this origin and so needs no exception.
 *
 * A `data-` attribute rather than a class, deliberately. React owns
 * `className` — it is a prop it will rewrite on the first re-render, taking
 * the injected name with it — and owns nothing here. On hydration React
 * applies its own `style` prop through the CSSOM, which is allowed, so the
 * element ends up styled by the rule before hydration and by React after,
 * with the same declarations either way.
 */
const PRERENDER_CSS = "/prerender.css";
const styleRules = new Map<string, number>();

function liftInlineStyles(markup: string): string {
  return markup.replace(/ style="([^"]*)"/g, (_match, declarations: string) => {
    if (!styleRules.has(declarations)) styleRules.set(declarations, styleRules.size);
    return ` data-bs="${styleRules.get(declarations)}"`;
  });
}

function styleSheet(): string {
  return [...styleRules]
    .map(([declarations, index]) => `[data-bs="${index}"]{${decodeEntities(declarations)}}`)
    .join("\n");
}

/** The markup is HTML, so its style values arrive escaped. CSS wants them raw. */
function decodeEntities(value: string): string {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function head(page: Page): string {
  const canonical = `${SITE_ORIGIN}${page.path}`;
  return [
    `<title>${escapeAttr(page.title)}</title>`,
    `<meta name="description" content="${escapeAttr(page.description)}" />`,
    `<link rel="canonical" href="${canonical}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="${SITE_NAME}" />`,
    `<meta property="og:url" content="${canonical}" />`,
    `<meta property="og:title" content="${escapeAttr(page.title)}" />`,
    `<meta property="og:description" content="${escapeAttr(page.description)}" />`,
    `<meta name="twitter:card" content="summary" />`,
    `<meta name="twitter:title" content="${escapeAttr(page.title)}" />`,
    `<meta name="twitter:description" content="${escapeAttr(page.description)}" />`,
    `<link rel="alternate" type="text/markdown" href="${markdownPath(page)}" />`,
    `<link rel="stylesheet" href="${PRERENDER_CSS}" />`,
    `<script type="application/ld+json">${structuredData(page)}</script>`,
  ].join("\n    ");
}

/**
 * Swap the shell's own head tags for this page's.
 *
 * Written as replacements of the specific tags the entry document declares
 * rather than as a blanket rewrite of `<head>`, so a tag added to
 * `index.html` — a preload, a verification token — survives rather than being
 * silently dropped by a tool nobody thought to update.
 */
function document(page: Page, markup: string): string {
  let html = shell;
  html = html.replace(/<title>.*?<\/title>/s, "@@HEAD@@");
  html = html.replace(/\n\s*<meta\s+name="description"[\s\S]*?\/>/, "");
  html = html.replace(/\n\s*<meta\s+property="og:[\s\S]*?\/>/g, "");
  html = html.replace(/\n\s*<meta\s+name="twitter:[\s\S]*?\/>/g, "");
  html = html.replace("@@HEAD@@", head(page));
  html = html.replace('<div id="root"></div>', `<div id="root">${liftInlineStyles(markup)}</div>`);
  return html;
}

/*
 * One page per scenario, at the URL the case explorer already links.
 *
 * These existed as fragments and were not documents, so prerendering left them
 * 404ing — the server had nothing at `/playground/<id>` and answered with the
 * not-found page, over which the client then rendered the playground. That
 * mismatch is what React was reporting; the missing document was the cause.
 *
 * They are worth having as pages in their own right rather than as a patch.
 * Each one is a recorded run of a real agent against a named scenario, and the
 * question the scenario asks — "Can it tidy a folder without destroying
 * anything?" — is a better title than any phrase invented for the purpose,
 * because it is what somebody would actually ask.
 */
const scenarioPages: Page[] = scenarios.map((scenario) => {
  /*
   * `id` for the URL, `slug` for the copy, and they are not always the same
   * word: the inbox scenario is `inbox-briefing-draft-only` by id and
   * `inbox-briefing` by slug. The case explorer links the id, and the router
   * matches ids, so the id is what a page has to be built at — building the
   * slug produced seven pages of which one was a URL nothing pointed to,
   * resolving to not-found, while the URL that *was* linked had no page.
   */
  const copy = scenarioCopy[scenario.slug];
  const question = copy?.question ?? scenario.name;
  return {
    route: "playground",
    path: `/playground/${scenario.id}`,
    title: `${question} — ${SITE_NAME}`,
    description: copy
      ? `${copy.tests} Graded on ${scenario.graded_on}; it fails when ${copy.fails
          .charAt(0)
          .toLowerCase()}${copy.fails.slice(1)} Replay the recorded runs, check by check.`
      : `A recorded run of ${scenario.name}, replayed check by check.`,
    changefreq: "monthly",
    priority: "0.6",
  };
});

const ALL: Page[] = [...PAGES, ...scenarioPages];

/**
 * Where a page's markdown twin lives: the same path with `.md` on it.
 *
 * `/` becomes `/index.md` because a directory cannot also be a file. Every
 * other route already ends in a segment, so `/docs` becomes `/docs.md` — a URL
 * anyone can guess, and one a person can open as readily as a model. That is
 * the whole difference between this and serving machines a private edition:
 * there is no audience test anywhere in it, only a format.
 */
function markdownPath(page: Page): string {
  return page.path === "/" ? "/index.md" : `${page.path}.md`;
}

/**
 * The twin: front matter a model can trust, then the page.
 *
 * The header is not decoration. A markdown file arriving without its canonical
 * URL is a fragment with no way back to the thing it describes, and a model
 * quoting it has nothing to cite.
 */
function markdownFor(page: Page, markup: string, others: Page[]): string {
  /*
   * From <main> through the footer, not <main> alone.
   *
   * The header is navigation and repeats on every page, so it goes. The footer
   * does not: it carries the sentence that a passing report is not a safety
   * certification, on every page, which is the one line that has to survive
   * into anything a model quotes. Taking only <main> dropped it from all
   * eleven twins — caught by the test that looks for it.
   */
  const from = markup.indexOf("<main");
  const to = markup.lastIndexOf("</footer>");
  const body = toMarkdown(markup.slice(from, to === -1 ? undefined : to + "</footer>".length));
  const links = others
    .filter((other) => other.path !== page.path)
    .map((other) => `- [${other.title}](${SITE_ORIGIN}${markdownPath(other)})`)
    .join("\n");

  return [
    "---",
    `title: ${page.title}`,
    `description: ${page.description}`,
    `canonical: ${SITE_ORIGIN}${page.path}`,
    `source: ${REPO}`,
    `licence: Apache-2.0`,
    "---",
    "",
    body.trim(),
    "",
    "## Other pages",
    "",
    links,
    "",
  ].join("\n");
}

const written: string[] = [];
for (const page of ALL) {
  const markup = render(page);

  const target = page.path === "/" ? join(DIST, "index.html") : join(DIST, page.path, "index.html");
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, document(page, markup));

  const twin = join(DIST, markdownPath(page));
  mkdirSync(dirname(twin), { recursive: true });
  writeFileSync(twin, markdownFor(page, markup, ALL));

  written.push(page.path);
}

/*
 * A 404 document, prerendered like any other and deliberately absent from the
 * sitemap. Vercel serves it with a 404 status, so an unrecognised path is
 * reported as missing rather than answered with the landing page — which is
 * what the old catch-all did, and it invites a crawler to index the same page
 * under every misspelling anyone links.
 */
(globalThis as { __BEACON_PRERENDER_PATH__?: string }).__BEACON_PRERENDER_PATH__ = "/not-a-page";
const notFound = shell
  .replace(
    /<title>.*?<\/title>/s,
    // No canonical, no structured data and no markdown twin: this document's
    // URL is whatever the visitor mistyped, so there is nothing true to
    // declare about it and nothing worth handing a model.
    `<title>Page not found — ${SITE_NAME}</title>\n    ` +
      '<meta name="robots" content="noindex, follow" />\n    ' +
      `<link rel="stylesheet" href="${PRERENDER_CSS}" />`,
  )
  .replace(/\n\s*<meta\s+property="og:[\s\S]*?\/>/g, "")
  .replace('<div id="root"></div>', `<div id="root">${liftInlineStyles(renderToString(<SiteB />))}</div>`);
writeFileSync(join(DIST, "404.html"), notFound);

writeFileSync(
  join(DIST, "prerender.css"),
  `/* Generated by tools/prerender.tsx: the inline styles the markup would\n`
    + ` * otherwise carry as attributes, which \`style-src 'self'\` forbids.\n */\n`
    + `${styleSheet()}\n`,
);

const SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9";
const entries = ALL.map(
  (page) => `  <url>
    <loc>${SITE_ORIGIN}${page.path}</loc>
    <changefreq>${page.changefreq}</changefreq>
    <priority>${page.priority}</priority>
  </url>`,
).join("\n");

writeFileSync(
  join(DIST, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="${SITEMAP_NS}">\n${entries}\n</urlset>\n`,
);

/*
 * `llms.txt`, and an honest note about what it is.
 *
 * A proposed convention rather than a standard, and crawler uptake is unproven
 * — it is here because it costs one file and is inert if nothing reads it. The
 * value is not the format: it is that the authoritative documents for this
 * project are in a repository, and a model that finds the marketing site first
 * should be pointed at them rather than left to infer the project from a
 * landing page.
 */
const llms = [
  `# ${SITE_NAME}`,
  "",
  `> ${PAGES[0].description}`,
  "",
  "Beacon is Apache-2.0, Python 3.11+, and standard library only. It contains no",
  "model and never calls one: grading is string and state comparison against",
  "assertions declared before the run. Every page on this site is also served as",
  "markdown at the same path with `.md` appended — the same content, not a",
  "different edition for machines.",
  "",
  "## Pages",
  "",
  ...ALL.map((page) => `- [${page.title}](${SITE_ORIGIN}${markdownPath(page)}): ${page.description}`),
  "",
  "## Source",
  "",
  `- [Repository](${REPO}): the harness, the scenarios, and this site.`,
  `- [Production readiness ledger](${REPO}/blob/main/docs/production-readiness.md): what Beacon is ready to be trusted with and what it is not, one limitation at a time.`,
  `- [Protocol contracts](${REPO}/blob/main/docs/protocol-contracts.md): what Beacon sends and expects over MCP, A2A and the JSONL bridge.`,
  `- [Architecture](${REPO}/blob/main/docs/architecture.md): the run lifecycle and the boundary that keeps the core ignorant of any model provider.`,
  "",
  "## Answers",
  "",
  ...FAQ.flatMap(({ q, a }) => [`### ${q}`, "", a, ""]),
].join("\n");

writeFileSync(join(DIST, "llms.txt"), llms);

/*
 * Everything is allowed, named rather than implied.
 *
 * `User-agent: *` already permitted every one of these, so listing them adds
 * no permission — it records that the permission is a decision. A project
 * arguing that agent behaviour should be inspectable has a weak position from
 * which to hide its own pages from the agents, and the whole repository is
 * Apache-2.0 and public: refusing a crawler would withhold nothing it could
 * not clone.
 *
 * The crawlers are split by what they do, because that is the distinction a
 * publisher would draw if it wanted to draw one, and a reader should be able
 * to see that it was considered and declined.
 */
writeFileSync(
  join(DIST, "robots.txt"),
  `# Every page here is prerendered, so nothing needs JavaScript to be read,
# and every page is also served as markdown: append .md to any path.
# Index for models: ${SITE_ORIGIN}/llms.txt

User-agent: *
Allow: /

# Named deliberately. These are the crawlers a publisher would consider
# refusing — training corpora, retrieval for assistants — and this project
# does not refuse them. Nothing here is served differently to any of them.
User-agent: GPTBot
User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: ClaudeBot
User-agent: Claude-Web
User-agent: anthropic-ai
User-agent: PerplexityBot
User-agent: Google-Extended
User-agent: CCBot
User-agent: Applebot-Extended
User-agent: Bytespider
User-agent: meta-externalagent
Allow: /

Sitemap: ${SITE_ORIGIN}/sitemap.xml
`,
);

console.log(`prerendered ${written.length} pages:`);
for (const path of written) console.log(`  ${path}`);
console.log(`  plus 404.html, sitemap.xml and robots.txt`);
