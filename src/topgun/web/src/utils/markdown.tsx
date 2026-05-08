import React from "react";

export function inlineFormat(text: string): React.ReactNode {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="font-mono text-xs text-green-live bg-card px-1 border border-border-dim">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-text-primary font-semibold">{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export function renderMarkdown(md: string): React.ReactNode[] {
  const lines = md.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <div key={key++} className="my-3">
          {lang && (
            <div className="font-mono text-xs text-text-muted tracking-widest px-3 py-1 border-t border-l border-r border-border-dim bg-card/50">
              {lang}
            </div>
          )}
          <pre className="font-mono text-xs text-green-live bg-card border border-border-dim px-4 py-3 overflow-x-auto whitespace-pre">
            {codeLines.join("\n")}
          </pre>
        </div>
      );
      i++;
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      nodes.push(
        <div key={key++} className="border-l-2 border-amber-tac/40 pl-4 my-2">
          <p className="font-mono text-xs text-text-muted italic">{inlineFormat(line.slice(2))}</p>
        </div>
      );
      i++;
      continue;
    }

    // H1
    if (line.startsWith("# ")) {
      nodes.push(
        <h1 key={key++} className="font-mono text-base font-bold text-text-primary mt-6 mb-2 tracking-wide">
          {line.slice(2)}
        </h1>
      );
      i++;
      continue;
    }

    // H2
    if (line.startsWith("## ")) {
      nodes.push(
        <h2 key={key++} className="font-mono text-sm font-semibold text-amber-tac mt-5 mb-1.5 tracking-widest uppercase">
          {line.slice(3)}
        </h2>
      );
      i++;
      continue;
    }

    // H3
    if (line.startsWith("### ")) {
      nodes.push(
        <h3 key={key++} className="font-mono text-xs font-semibold text-text-primary mt-3 mb-1 tracking-widest">
          {line.slice(4)}
        </h3>
      );
      i++;
      continue;
    }

    // Table (starts with |)
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!lines[i].match(/^\|[-| ]+\|$/)) {
          rows.push(lines[i].split("|").slice(1, -1).map(c => c.trim()));
        }
        i++;
      }
      nodes.push(
        <div key={key++} className="my-4 overflow-x-auto">
          <table className="font-mono text-xs w-full border-collapse">
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className={ri === 0 ? "border-b border-amber-tac/40" : "border-b border-border-dim"}>
                  {row.map((cell, ci) => (
                    <td key={ci} className={`px-4 py-1.5 ${ri === 0 ? "text-amber-tac tracking-widest" : "text-text-primary"}`}>
                      {inlineFormat(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Bullet list
    if (line.match(/^[-*] /)) {
      nodes.push(
        <div key={key++} className="flex gap-3 my-0.5">
          <span className="font-mono text-xs text-amber-tac/60 shrink-0">·</span>
          <span className="font-mono text-xs text-text-primary leading-relaxed">{inlineFormat(line.slice(2))}</span>
        </div>
      );
      i++;
      continue;
    }

    // Numbered list
    const numMatch = line.match(/^(\d+)\. (.+)/);
    if (numMatch) {
      nodes.push(
        <div key={key++} className="flex gap-3 my-0.5">
          <span className="font-mono text-xs text-amber-tac/60 shrink-0 w-4">{numMatch[1]}.</span>
          <span className="font-mono text-xs text-text-primary leading-relaxed">{inlineFormat(numMatch[2])}</span>
        </div>
      );
      i++;
      continue;
    }

    // Blank line
    if (line.trim() === "") {
      nodes.push(<div key={key++} className="h-2" />);
      i++;
      continue;
    }

    // Paragraph
    nodes.push(
      <p key={key++} className="font-mono text-xs text-text-primary leading-relaxed">
        {inlineFormat(line)}
      </p>
    );
    i++;
  }

  return nodes;
}
