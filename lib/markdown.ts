/**
 * Markdown normalisation + parsing for the Canvas.
 *
 * Job descriptions reach us in three shapes depending on the ATS scraped:
 *   - Greenhouse: HTML, entity-escaped once (`&lt;p&gt;…`)
 *   - Lever:      plain text with `-` / `•` bullets
 *   - Alice:      genuine Markdown
 * Everything is funnelled through `normalizeToMarkdown` so the Canvas only ever
 * renders Markdown — tags are converted or dropped, never injected as HTML.
 */

const NAMED_ENTITIES: Record<string, string> = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
  hellip: "…", mdash: "—", ndash: "–", laquo: "«", raquo: "»",
  rsquo: "’", lsquo: "‘", ldquo: "“", rdquo: "”", bull: "•", middot: "·",
  eacute: "é", egrave: "è", ecirc: "ê", euml: "ë",
  agrave: "à", acirc: "â", auml: "ä", ccedil: "ç",
  ugrave: "ù", ucirc: "û", uuml: "ü", ocirc: "ô", ouml: "ö",
  icirc: "î", iuml: "ï", szlig: "ß",
  deg: "°", euro: "€", pound: "£", copy: "©", reg: "®", trade: "™",
};

function decodeEntities(input: string): string {
  return input.replace(/&(#x?[0-9a-f]+|[a-z][a-z0-9]*);/gi, (match, body: string) => {
    if (body.startsWith("#")) {
      const codePoint =
        body[1] === "x" || body[1] === "X"
          ? parseInt(body.slice(2), 16)
          : parseInt(body.slice(1), 10);
      if (!Number.isFinite(codePoint) || codePoint <= 0 || codePoint > 0x10ffff) return match;
      try {
        return String.fromCodePoint(codePoint);
      } catch {
        return match;
      }
    }
    return NAMED_ENTITIES[body.toLowerCase()] ?? match;
  });
}

function htmlToMarkdown(html: string): string {
  let out = html;

  // Non-content elements go away with their contents.
  out = out.replace(/<(script|style|noscript|iframe|svg|head)\b[^>]*>[\s\S]*?<\/\1>/gi, "");

  out = out.replace(/<br\s*\/?>/gi, "\n");

  // Lists before the generic block rule, so bullets stay in one list.
  out = out.replace(/<\/li\s*>/gi, "\n");
  out = out.replace(/<li\b[^>]*>/gi, "\n- ");
  out = out.replace(/<\/?(ul|ol)\b[^>]*>/gi, "\n\n");

  out = out.replace(/<\/h[1-6]\s*>/gi, "\n\n");
  out = out.replace(/<h([1-6])\b[^>]*>/gi, (_m, level: string) => {
    // Demote one level: the Canvas already owns the h1/h2 of the page.
    const hashes = "#".repeat(Math.min(Number(level) + 1, 6));
    return `\n\n${hashes} `;
  });

  out = out.replace(/<hr\s*\/?>/gi, "\n\n---\n\n");
  out = out.replace(/<\/(p|div|section|article|blockquote|tr|table)\s*>/gi, "\n\n");

  out = out.replace(
    /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a\s*>/gi,
    (_m, href: string, label: string) => {
      const text = label.replace(/<[^>]+>/g, "").trim();
      return text ? `[${text}](${href})` : href;
    },
  );

  out = out.replace(/<\/?(strong|b)\b[^>]*>/gi, "**");
  out = out.replace(/<\/?(em|i)\b[^>]*>/gi, "*");
  out = out.replace(/<\/?code\b[^>]*>/gi, "`");

  // Anything still tag-shaped is discarded — nothing HTML survives this point.
  out = out.replace(/<[^>]+>/g, "");

  return out;
}

export function normalizeToMarkdown(raw: string | null | undefined): string {
  if (!raw) return "";

  let text = decodeEntities(raw);
  if (/<\/?[a-z][^>]*>/i.test(text)) {
    text = decodeEntities(htmlToMarkdown(text));
  }

  return text
    .replace(/\r\n?/g, "\n")
    .replace(/^[ \t]*[•▪●·]\s+/gm, "- ")
    .replace(/[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// ── Block parsing ──────────────────────────────────────────────────────────

export type MdBlock =
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "code"; lang: string; text: string }
  | { kind: "hr" }
  | { kind: "para"; text: string };

const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const UL_RE = /^\s{0,3}[-*+]\s+(.*)$/;
const OL_RE = /^\s{0,3}\d+[.)]\s+(.*)$/;
const QUOTE_RE = /^\s{0,3}>\s?(.*)$/;
const HR_RE = /^\s{0,3}([-*_])\s*(?:\1\s*){2,}$/;
const FENCE_RE = /^\s{0,3}```\s*(\S*)\s*$/;

export function parseMarkdown(source: string): MdBlock[] {
  const lines = source.split("\n");
  const blocks: MdBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i++;
      continue;
    }

    const fence = line.match(FENCE_RE);
    if (fence) {
      const lang = fence[1] || "";
      const body: string[] = [];
      i++;
      while (i < lines.length && !FENCE_RE.test(lines[i])) body.push(lines[i++]);
      i++; // closing fence
      blocks.push({ kind: "code", lang, text: body.join("\n") });
      continue;
    }

    if (HR_RE.test(line)) {
      blocks.push({ kind: "hr" });
      i++;
      continue;
    }

    const heading = line.match(HEADING_RE);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2].trim() });
      i++;
      continue;
    }

    if (QUOTE_RE.test(line)) {
      const body: string[] = [];
      while (i < lines.length && QUOTE_RE.test(lines[i])) {
        body.push(lines[i].match(QUOTE_RE)![1]);
        i++;
      }
      blocks.push({ kind: "quote", text: body.join("\n").trim() });
      continue;
    }

    const isOrdered = OL_RE.test(line);
    if (isOrdered || UL_RE.test(line)) {
      const items: string[] = [];
      const itemRe = isOrdered ? OL_RE : UL_RE;
      while (i < lines.length) {
        const match = lines[i].match(itemRe);
        if (match) {
          items.push(match[1].trim());
          i++;
        } else if (lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length) {
          // Continuation line of the previous bullet.
          items[items.length - 1] += ` ${lines[i].trim()}`;
          i++;
        } else {
          break;
        }
      }
      blocks.push({ kind: "list", ordered: isOrdered, items });
      continue;
    }

    const body: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !HEADING_RE.test(lines[i]) &&
      !UL_RE.test(lines[i]) &&
      !OL_RE.test(lines[i]) &&
      !QUOTE_RE.test(lines[i]) &&
      !HR_RE.test(lines[i]) &&
      !FENCE_RE.test(lines[i])
    ) {
      body.push(lines[i].trim());
      i++;
    }
    blocks.push({ kind: "para", text: body.join("\n") });
  }

  return blocks;
}

// ── Inline parsing ─────────────────────────────────────────────────────────

export type MdInline =
  | { kind: "text"; text: string }
  | { kind: "break" }
  | { kind: "strong"; children: MdInline[] }
  | { kind: "em"; children: MdInline[] }
  | { kind: "code"; text: string }
  | { kind: "link"; href: string; children: MdInline[] };

const INLINE_RE =
  /(\*\*|__)([\s\S]+?)\1|(\*|_)([^*_\n][\s\S]*?)\3|`([^`\n]+)`|\[([^\]]*)\]\(([^)\s]+)\)|(https?:\/\/[^\s<>()[\]]+)/;

/** Only http(s) and mailto survive — never `javascript:` from a scraped page. */
export function safeHref(href: string): string | null {
  const trimmed = href.trim();
  return /^(https?:\/\/|mailto:)/i.test(trimmed) ? trimmed : null;
}

export function parseInline(text: string): MdInline[] {
  const nodes: MdInline[] = [];
  let rest = text;

  const pushText = (chunk: string) => {
    if (!chunk) return;
    const parts = chunk.split("\n");
    parts.forEach((part, idx) => {
      if (idx > 0) nodes.push({ kind: "break" });
      if (part) nodes.push({ kind: "text", text: part });
    });
  };

  while (rest) {
    const match = rest.match(INLINE_RE);
    if (!match || match.index === undefined) {
      pushText(rest);
      break;
    }

    pushText(rest.slice(0, match.index));

    const [full, , strongBody, , emBody, codeBody, linkLabel, linkHref, autolink] = match;

    if (strongBody !== undefined) {
      nodes.push({ kind: "strong", children: parseInline(strongBody) });
    } else if (emBody !== undefined) {
      nodes.push({ kind: "em", children: parseInline(emBody) });
    } else if (codeBody !== undefined) {
      nodes.push({ kind: "code", text: codeBody });
    } else if (linkHref !== undefined) {
      const href = safeHref(linkHref);
      const children = parseInline(linkLabel || linkHref);
      nodes.push(href ? { kind: "link", href, children } : { kind: "text", text: linkLabel || linkHref });
    } else if (autolink !== undefined) {
      nodes.push({ kind: "link", href: autolink, children: [{ kind: "text", text: autolink }] });
    }

    rest = rest.slice(match.index + full.length);
  }

  return nodes;
}
