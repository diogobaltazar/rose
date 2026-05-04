import { useAuth0 } from "@auth0/auth0-react";
import { Link, useLocation } from "react-router-dom";

export default function NavBar() {
  const { user, logout } = useAuth0();
  const location = useLocation();

  return (
    <nav className="relative z-20 flex items-center justify-between px-6 py-4 border-b border-border-dim bg-base/80 backdrop-blur-sm">
      <Link to="/deck" className="font-mono text-sm font-bold tracking-[0.35em] text-amber-tac hover:text-amber-dim transition-colors">
        TOPGUN
      </Link>

      <div className="flex items-center gap-2 text-xs">
        {location.pathname !== "/deck" && (
          <Link to="/deck" className="font-mono text-text-secondary hover:text-amber-tac transition-colors tracking-widest uppercase mr-4">
            Deck
          </Link>
        )}
        <Link
          to="/deck/connections"
          className={`font-mono tracking-widest uppercase transition-colors mr-2 ${
            location.pathname === "/deck/connections"
              ? "text-amber-tac"
              : "text-text-secondary hover:text-amber-tac"
          }`}
        >
          Connections
        </Link>
        {user && (
          <>
            <span className="font-mono text-text-muted tracking-wide">{user.email}</span>
            <span className="text-border-bright mx-2">|</span>
          </>
        )}
        <button
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          className="font-mono text-text-secondary hover:text-amber-tac transition-colors tracking-widest uppercase"
        >
          DEAUTH
        </button>
      </div>
    </nav>
  );
}
