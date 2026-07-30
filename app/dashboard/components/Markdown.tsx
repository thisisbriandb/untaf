"use client";

import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import {
  normalizeToMarkdown,
  parseInline,
  parseMarkdown,
  type MdInline,
} from "@/lib/markdown";

/**
 * Canvas Markdown renderer.
 *
 * Builds React elements from the parsed tree — no `dangerouslySetInnerHTML`,
 * so scraped third-party job descriptions can never inject markup or scripts.
 */

function renderInline(nodes: MdInline[], keyPrefix = ""): ReactNode[] {
  return nodes.map((node, i) => {
    const key = `${keyPrefix}${i}`;
    switch (node.kind) {
      case "text":
        return <Fragment key={key}>{node.text}</Fragment>;
      case "break":
        return <br key={key} />;
      case "strong":
        return (
          <strong key={key} className="font-medium text-[#1A1918]">
            {renderInline(node.children, `${key}-`)}
          </strong>
        );
      case "em":
        return (
          <em key={key} className="italic">
            {renderInline(node.children, `${key}-`)}
          </em>
        );
      case "code":
        return (
          <code
            key={key}
            className="px-1.5 py-0.5 rounded-md bg-[#1A1918]/6 font-mono text-[0.85em] text-[#1A1918]"
          >
            {node.text}
          </code>
        );
      case "link":
        return (
          <a
            key={key}
            href={node.href}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="text-[#006045] underline underline-offset-2 decoration-[#006045]/30 hover:decoration-[#006045] transition-colors break-words"
          >
            {renderInline(node.children, `${key}-`)}
          </a>
        );
    }
  });
}

const HEADING_SIZES: Record<number, string> = {
  1: "text-base font-medium",
  2: "text-[15px] font-medium",
  3: "text-sm font-medium",
  4: "text-sm font-normal",
  5: "text-[13px] font-normal",
  6: "text-[13px] font-normal",
};

export function Markdown({
  source,
  className,
}: {
  source: string | null | undefined;
  className?: string;
}) {
  const md = normalizeToMarkdown(source);

  if (!md) {
    return (
      <p className="text-sm font-light text-[#1A1918]/40 tracking-tight">
        Aucun contenu à afficher.
      </p>
    );
  }

  const blocks = parseMarkdown(md);

  return (
    <div
      className={cn(
        "space-y-3.5 text-sm font-light leading-relaxed tracking-tight text-[#1A1918]/75",
        className,
      )}
    >
      {blocks.map((block, i) => {
        const key = `b${i}`;
        switch (block.kind) {
          case "heading": {
            const Tag = `h${Math.min(block.level, 6)}` as "h1";
            return (
              <Tag
                key={key}
                className={cn(
                  "text-[#1A1918] tracking-tight pt-1.5",
                  HEADING_SIZES[block.level] ?? HEADING_SIZES[3],
                )}
              >
                {renderInline(parseInline(block.text), `${key}-`)}
              </Tag>
            );
          }

          case "list": {
            const ListTag = block.ordered ? "ol" : "ul";
            return (
              <ListTag key={key} className="space-y-1.5 pl-1">
                {block.items.map((item, j) => (
                  <li key={`${key}-${j}`} className="flex gap-2.5">
                    <span className="shrink-0 text-[#006045] tabular-nums select-none">
                      {block.ordered ? `${j + 1}.` : "—"}
                    </span>
                    <span className="min-w-0 flex-1">
                      {renderInline(parseInline(item), `${key}-${j}-`)}
                    </span>
                  </li>
                ))}
              </ListTag>
            );
          }

          case "quote":
            return (
              <blockquote
                key={key}
                className="border-l-2 border-[#006045]/30 pl-3.5 text-[#1A1918]/60 italic"
              >
                {renderInline(parseInline(block.text), `${key}-`)}
              </blockquote>
            );

          case "code":
            return (
              <pre
                key={key}
                className="scroll-discreet overflow-x-auto rounded-xl border border-[#1A1918]/8 bg-[#FAFAF8] p-3.5 text-xs font-mono leading-relaxed text-[#1A1918]/80"
              >
                <code>{block.text}</code>
              </pre>
            );

          case "hr":
            return <hr key={key} className="border-t border-[#1A1918]/8" />;

          case "para":
            return (
              <p key={key}>{renderInline(parseInline(block.text), `${key}-`)}</p>
            );
        }
      })}
    </div>
  );
}
