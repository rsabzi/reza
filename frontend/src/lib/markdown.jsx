import { Fragment } from "react";

/**
 * Minimal, safe rich-text renderer for assistant messages.
 * Supports **bold**, *italic*, `code`, headings (###/####), lists (-/*),
 * numbered lists (1.) and plain URLs — everything else is escaped text.
 */
const CODE_SPAN = /(`[^`\n]+`)/g;
const INLINE = /(\*\*[^*]+\*\*|\*[^*\n]+\*)/g;
const URL = /(https?:\/\/[^\s<]+[^\s.,،:;)\]}>])/g;

function renderInline(text, keyPrefix) {
  const nodes = [];
  let cursor = 0;
  const combined = new RegExp(
    `(${CODE_SPAN.source}|${INLINE.source})`,
    "g",
  );
  let match;
  const slice = String(text);
  while ((match = combined.exec(slice)) !== null) {
    if (match.index > cursor) {
      nodes.push(<Fragment key={`${keyPrefix}-t${cursor}`}>{slice.slice(cursor, match.index)}</Fragment>);
    }
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(
        <code key={`${keyPrefix}-c${match.index}`}>{token.slice(1, -1)}</code>,
      );
    } else if (token.startsWith("**")) {
      nodes.push(
        <strong key={`${keyPrefix}-b${match.index}`}>{token.slice(2, -2)}</strong>,
      );
    } else {
      nodes.push(
        <em key={`${keyPrefix}-i${match.index}`}>{token.slice(1, -1)}</em>,
      );
    }
    cursor = match.index + token.length;
  }
  if (cursor < slice.length) {
    nodes.push(
      <Fragment key={`${keyPrefix}-tail`}>{slice.slice(cursor)}</Fragment>,
    );
  }
  return nodes;
}

function withLinks(children, keyPrefix) {
  // Walk fragments and convert URL runs into anchors.
  return children.map((node, index) => {
    if (typeof node.props?.children !== "string") return node;
    const text = node.props.children;
    if (!URL.test(text)) return node;
    const parts = text.split(URL);
    return (
      <Fragment key={`${keyPrefix}-u${index}`}>
        {parts.map((part, partIndex) =>
          partIndex % 2 === 1 ? (
            <a
              key={`${keyPrefix}-a${partIndex}`}
              href={part}
              target="_blank"
              rel="noreferrer"
            >
              {part}
            </a>
          ) : (
            <Fragment key={`${keyPrefix}-p${partIndex}`}>{part}</Fragment>
          ),
        )}
      </Fragment>
    );
  });
}

export function RichText({ text, className = "" }) {
  if (!text) return null;
  const lines = String(text).split(/\r?\n/);
  const blocks = [];
  let listBuffer = null; // { type: "ul" | "ol", items: [] }
  let listKey = 0;

  const flushList = () => {
    if (!listBuffer) return;
    const items = listBuffer.items.map((item, itemIndex) => (
      <li key={`${listKey}-li${itemIndex}`}>
        {withLinks(renderInline(item, `${listKey}-li${itemIndex}`), `${listKey}-li${itemIndex}`)}
      </li>
    ));
    blocks.push(
      listBuffer.type === "ul" ? (
        <ul key={`${listKey}-ul`}>{items}</ul>
      ) : (
        <ol key={`${listKey}-ol`}>{items}</ol>
      ),
    );
    listBuffer = null;
    listKey += 1;
  };

  lines.forEach((line, lineIndex) => {
    const trimmed = line.trim();
    const key = `l${lineIndex}`;

    if (!trimmed) {
      flushList();
      return;
    }
    const heading = trimmed.match(/^#{2,4}\s+(.+)$/);
    if (heading) {
      flushList();
      blocks.push(
        <h4 key={`${key}-h`}>
          {withLinks(renderInline(heading[1], `${key}-h`), `${key}-h`)}
        </h4>,
      );
      return;
    }
    const bullet = trimmed.match(/^[-•]\s+(.+)$/);
    if (bullet) {
      if (!listBuffer || listBuffer.type !== "ul") {
        flushList();
        listBuffer = { type: "ul", items: [] };
      }
      listBuffer.items.push(bullet[1]);
      return;
    }
    const numbered = trimmed.match(/^(\d+)[.)]\s+(.+)$/);
    if (numbered) {
      if (!listBuffer || listBuffer.type !== "ol") {
        flushList();
        listBuffer = { type: "ol", items: [] };
      }
      listBuffer.items.push(numbered[2]);
      return;
    }
    flushList();
    blocks.push(
      <p key={`${key}-p`} className="min-h-[1em]">
        {withLinks(renderInline(trimmed, key), key)}
      </p>,
    );
  });
  flushList();

  return <div className={`rich-text ${className}`}>{blocks}</div>;
}
