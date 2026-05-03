interface Props {
  status: "live" | "done" | "open" | "closed";
  label?: string;
}

const cfg = {
  live:   { dot: "bg-green-live animate-pulse_amber", text: "text-green-live", label: "LIVE" },
  done:   { dot: "bg-text-muted", text: "text-text-secondary", label: "DONE" },
  open:   { dot: "bg-amber-tac animate-pulse_amber", text: "text-amber-tac", label: "OPEN" },
  closed: { dot: "bg-text-muted", text: "text-text-secondary", label: "CLOSED" },
};

export default function StatusPip({ status, label }: Props) {
  const c = cfg[status];
  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-xs ${c.text}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {label ?? c.label}
    </span>
  );
}
