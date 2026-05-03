import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";

export default function Callback() {
  const { isLoading, isAuthenticated, error } = useAuth0();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [isLoading, isAuthenticated, navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <div className="tac-border p-8 text-center bracket-corners max-w-sm">
          <p className="font-mono text-xs text-red-alert mb-2 tracking-widest">AUTH FAILURE</p>
          <p className="font-mono text-xs text-text-muted">{error.message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center">
      <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
        AUTHENTICATING...
      </span>
    </div>
  );
}
