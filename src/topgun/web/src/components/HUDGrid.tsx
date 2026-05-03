export default function HUDGrid() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden>
      {/* Dot grid */}
      <div
        className="absolute inset-0 bg-dot-grid bg-dot-md opacity-100"
        style={{ backgroundImage: "radial-gradient(circle, rgba(255,184,0,0.07) 1px, transparent 1px)" }}
      />
      {/* Horizontal scan line */}
      <div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-amber-tac/20 to-transparent animate-scanline"
        style={{ top: 0 }}
      />
      {/* Vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(0,0,0,0.7)_100%)]" />
    </div>
  );
}
