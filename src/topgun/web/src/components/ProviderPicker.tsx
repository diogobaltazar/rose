interface Provider {
  id: string;
  name: string;
  detail: string;
  available: boolean;
  enterprise?: boolean;
}

interface Props {
  providers: Provider[];
  selected: string;
  onSelect: (id: string) => void;
  hasEnterprise?: boolean;
}

export default function ProviderPicker({ providers, selected, onSelect, hasEnterprise = false }: Props) {
  const current = providers.find(p => p.id === selected);

  return (
    <div className="relative mb-5">
      <select
        value={selected}
        onChange={e => onSelect(e.target.value)}
        className="w-full appearance-none bg-card border border-border-dim px-3 py-2 pr-8 font-mono text-xs text-text-primary focus:outline-none focus:border-amber-tac cursor-pointer"
      >
        {providers.map(p => {
          const isEnterprise = p.enterprise === true;
          const isAvailable = p.available || (isEnterprise && hasEnterprise);
          const suffix = isEnterprise && !hasEnterprise
            ? " — Enterprise"
            : !p.available && !isEnterprise
              ? " — Coming soon"
              : "";
          return (
            <option key={p.id} value={p.id} disabled={!isAvailable}>
              {p.name}{suffix}
            </option>
          );
        })}
      </select>

      {/* Custom chevron */}
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[10px] text-amber-tac/60">
        ▾
      </span>

      {/* Detail line for selected provider */}
      {current && (
        <p className="font-mono text-[10px] text-text-muted mt-1.5 px-1">
          {current.detail}
          {current.enterprise && !hasEnterprise && (
            <span className="ml-2 text-amber-tac/40">· Included with ALMA VICTORIA Enterprise</span>
          )}
        </p>
      )}
    </div>
  );
}
