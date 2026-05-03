import { useEffect, useState, useRef } from "react";

interface Props {
  lines: string[];
  typingSpeed?: number;
}

export default function Terminal({ lines, typingSpeed = 38 }: Props) {
  const [displayed, setDisplayed] = useState<string[]>([]);
  const [currentLine, setCurrentLine] = useState(0);
  const [currentChar, setCurrentChar] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (currentLine >= lines.length) return;
    const line = lines[currentLine];
    if (currentChar < line.length) {
      timerRef.current = setTimeout(() => {
        setCurrentChar((c) => c + 1);
      }, typingSpeed);
    } else {
      timerRef.current = setTimeout(() => {
        setDisplayed((d) => [...d, line]);
        setCurrentLine((l) => l + 1);
        setCurrentChar(0);
      }, 300);
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [currentLine, currentChar, lines, typingSpeed]);

  const inProgress = currentLine < lines.length ? lines[currentLine].slice(0, currentChar) : null;

  return (
    <div className="tac-border bg-[#0a0a0a] p-5 bracket-corners font-mono text-sm leading-relaxed">
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-border-dim">
        <span className="w-2.5 h-2.5 rounded-full bg-red-alert/60" />
        <span className="w-2.5 h-2.5 rounded-full bg-amber-tac/60" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-live/60" />
        <span className="ml-2 text-xs text-text-muted tracking-widest">TERMINAL</span>
      </div>
      {displayed.map((line, i) => (
        <div key={i} className={line.startsWith("//") ? "text-text-muted" : line.startsWith("$") ? "text-amber-tac" : "text-text-secondary"}>
          {line}
        </div>
      ))}
      {inProgress !== null && (
        <div className={lines[currentLine].startsWith("$") ? "text-amber-tac" : "text-text-secondary"}>
          {inProgress}
          <span className="animate-blink">▌</span>
        </div>
      )}
    </div>
  );
}
