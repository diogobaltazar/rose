import { useAuth0 } from "@auth0/auth0-react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { label: "MISSION DECK", path: "/deck/missions" },
  { label: "INTEL", path: "/deck/intel" },
  { label: "PILOTS", path: "/deck/pilots" },
];

export default function NavBar() {
  const { user, logout } = useAuth0();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="relative z-20 flex items-center justify-between px-6 py-3 border-b border-border-dim bg-base/80 backdrop-blur-sm">
      {/* Brand */}
      <Link to="/deck/missions" className="font-mono text-sm font-bold tracking-[0.3em] hover:opacity-80 transition-opacity shrink-0">
        <span className="text-white/70">ALMA VICTORIA</span>{" "}
        <span className="text-amber-tac">TOPGUN</span>
      </Link>

      {/* Nav items */}
      <div className="flex items-center gap-0 mx-6">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`font-mono text-xs px-4 py-2 tracking-widest transition-colors ${
              isActive(item.path)
                ? "text-amber-tac border-b border-amber-tac"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {item.label}
          </Link>
        ))}
      </div>

      {/* Right: user + settings + deauth */}
      <div className="flex items-center gap-3 shrink-0">
        {user && (
          <span className="font-mono text-xs text-amber-tac tracking-wide hidden sm:block">
            {user.email}
          </span>
        )}
        <Link
          to="/deck/settings"
          className={`font-mono text-xl leading-none flex items-center transition-colors ${
            isActive("/deck/settings") ? "text-amber-tac" : "text-text-muted hover:text-text-secondary"
          }`}
          title="Settings"
        >
          ⚙
        </Link>
        <button
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          className="font-mono text-xs text-text-muted hover:text-red-alert transition-colors tracking-widest uppercase"
        >
          DEAUTH
        </button>
      </div>
    </nav>
  );
}
