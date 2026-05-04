import { useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";

/**
 * Returns the best available JWT for API calls.
 *
 * When AUTH0_AUDIENCE is not configured (local dev), getAccessTokenSilently()
 * returns a JWE (encrypted opaque token) the API cannot validate. We fall
 * back to the id_token which is always a signed RS256 JWT.
 */
export function useToken() {
  const { getAccessTokenSilently, getIdTokenClaims } = useAuth0();

  const getToken = useCallback(async (): Promise<string> => {
    try {
      const token = await getAccessTokenSilently();
      if (token && isSignedJwt(token)) return token;
    } catch {
      // fall through
    }
    const claims = await getIdTokenClaims();
    return claims?.__raw ?? "";
  }, [getAccessTokenSilently, getIdTokenClaims]);

  return { getToken };
}

function isSignedJwt(token: string): boolean {
  // JWS (signed JWT) has 3 dot-separated parts and an asymmetric signing alg.
  // JWE (encrypted token) has 5 parts — the API cannot validate those.
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  try {
    const header = JSON.parse(atob(parts[0].replace(/-/g, "+").replace(/_/g, "/")));
    return ["RS256", "RS384", "RS512"].includes(header.alg);
  } catch {
    return false;
  }
}
