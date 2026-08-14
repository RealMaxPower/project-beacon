/**
 * Turn this site's own rendered markup into markdown.
 *
 * Not a general HTML converter and deliberately not a dependency. The input is
 * React's output for components in this repository, so the tag vocabulary is
 * known, closed, and changes only when somebody here changes it — which is the
 * condition under which a small transformation is safer than a large one. A
 * general converter would handle markup this site never emits and would fail
 * silently on the day it did.
 *
 * The point is the ratio. The landing page is 80KB of HTML carrying 18KB of
 * prose, so a model reading the site pays about four times the tokens it
 * needs. The point is *not* to say anything different: the markdown is a
 * rendering of the same page, generated in the same pass, and
 * `test_site_markdown.py` compares the claims in one against the other. A
 * machine-readable copy that can drift from the human one is two sets of
 * claims and one of them unreviewed, which is the thing this project exists to
 * refuse.
 */

/** Entities React emits, back to the characters they stand for. */
function decode(value: string): string {
  return value
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
}

/** Content a reader is never shown, and a model should not be either. */
function dropInvisible(html: string): string {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/g, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, "")
    // Icons and rules. Each one is decoration with no text a reader relies on.
    .replace(/<svg\b[^>]*>[\s\S]*?<\/svg>/g, "")
    .replace(/<[a-z]+\b[^>]*\saria-hidden="true"[^>]*>[\s\S]*?<\/[a-z]+>/g, "")
    .replace(/<[a-z]+\b[^>]*\saria-hidden="true"[^>]*\/?>/g, "");
}

/**
 * A fenced code block, with its newlines kept.
 *
 * Done before everything else because the general pass collapses whitespace,
 * and a shell transcript with its line breaks collapsed is a paragraph of
 * commands run together — worse than omitting it, because it still looks like
 * something a reader could copy.
 */
function fenceCode(html: string): string {
  return html.replace(/<pre\b[^>]*>([\s\S]*?)<\/pre>/g, (_all, inner: string) => {
    const text = decode(inner.replace(/<[^>]+>/g, ""));
    return `\n\n@@FENCE@@${text.trim()}@@FENCE@@\n\n`;
  });
}

export function toMarkdown(html: string): string {
  let out = fenceCode(dropInvisible(html));

  // Links first: the href is lost the moment tags are stripped.
  out = out.replace(
    /<a\b[^>]*\bhref="([^"]*)"[^>]*>([\s\S]*?)<\/a>/g,
    (_all, href: string, label: string) => {
      // A space for each tag here too: a card whose label is a filename span
      // beside a description span came out as `docs/architecture.mdThe run
      // lifecycle…`, which is a link nobody can read and a filename that does
      // not exist.
      const text = decode(label.replace(/<[^>]+>/g, " ")).replace(/\s+/g, " ").trim();
      if (!text) return "";
      // Padded for the same reason the tag strip below is: React puts no
      // whitespace between two adjacent anchors, so three buttons in a row
      // came out as one word with a URL in the middle of it.
      return href.startsWith("#") ? ` ${text} ` : ` [${text}](${href}) `;
    },
  );

  out = out.replace(/<code\b[^>]*>([\s\S]*?)<\/code>/g, (_all, inner: string) => {
    const text = decode(inner.replace(/<[^>]+>/g, "")).replace(/\s+/g, " ").trim();
    return text ? ` \`${text}\` ` : "";
  });

  // Headings, and the FAQ's <summary>, which is a question and reads as one.
  for (const [tag, hashes] of [
    ["h1", "#"],
    ["h2", "##"],
    ["h3", "###"],
    ["h4", "####"],
    ["summary", "###"],
  ] as const) {
    out = out.replace(
      new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)</${tag}>`, "g"),
      (_all, inner: string) => `\n\n${hashes} @@LINE@@${inner}@@LINE@@\n\n`,
    );
  }

  out = out.replace(/<li\b[^>]*>([\s\S]*?)<\/li>/g, (_all, inner: string) => `\n- @@LINE@@${inner}@@LINE@@`);

  // Everything else that ends a line.
  out = out.replace(/<\/(p|div|section|tr|ul|ol|details|header|footer|blockquote)>/g, "\n\n");
  out = out.replace(/<br\s*\/?>/g, "\n");

  /*
   * A space where a tag was, not nothing.
   *
   * Two adjacent inline elements have no whitespace between them in React's
   * output — it is the boundary that separates them — so deleting the tags
   * outright welded words together: `mail_send_draftBLOCKED`, `syntheticFAIL
   * 8/9`. A model reading that gets a token that appears nowhere on the page.
   * The collapse below removes whatever this over-inserts.
   */
  out = decode(out.replace(/<[^>]+>/g, " "));

  /*
   * Whitespace, in two passes that must stay in this order.
   *
   * A heading or a list item is one line however the JSX was indented, so its
   * contents collapse first, inside the markers placed above. Then the
   * document's blank lines are capped. Doing it the other way round runs a
   * wrapped heading into the paragraph after it.
   */
  out = out.replace(/@@LINE@@([\s\S]*?)@@LINE@@/g, (_all, inner: string) =>
    inner.replace(/\s+/g, " ").trim(),
  );
  out = out
    .split(/(@@FENCE@@[\s\S]*?@@FENCE@@)/)
    .map((chunk) =>
      chunk.startsWith("@@FENCE@@")
        ? `\`\`\`\n${chunk.replace(/@@FENCE@@/g, "").trim()}\n\`\`\``
        : chunk.replace(/[^\S\n]+/g, " ").replace(/ ?\n ?/g, "\n"),
    )
    .join("\n\n");

  return (
    out
      .replace(/\n{3,}/g, "\n\n")
      // Tidy what the space-for-a-tag rule leaves behind.
      .replace(/ +([,.;:!?)\]])/g, "$1")
      .replace(/([(\[]) +/g, "$1")
      /*
       * Rejoin a slash the tag strip split.
       *
       * `docs/` and `agent-builders.md` are adjacent spans with no whitespace
       * between them, and so are the filename and the description that follows
       * it — the same shape, meaning opposite things, and nothing in the markup
       * tells them apart. Inserting a space fixes the second and breaks the
       * first, so the first is repaired here: a path is the only thing on this
       * site that puts a slash between two words with no spaces around it.
       */
      .replace(/(\S) \/ (\S)/g, "$1/$2")
      .replace(/ +/g, " ")
      .replace(/ \n/g, "\n")
      .trim() + "\n"
  );
}
