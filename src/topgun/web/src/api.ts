import type { AppConfig, Mission, Engagement } from "./types";

const BASE = "/api";

export async function getConfig(): Promise<AppConfig> {
  const r = await fetch(`${BASE}/config`);
  if (!r.ok) throw new Error("config fetch failed");
  return r.json();
}

async function authFetch(url: string, token: string): Promise<Response> {
  return fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getMissions(token: string): Promise<Mission[]> {
  const r = await authFetch(`${BASE}/missions`, token);
  if (!r.ok) throw new Error("missions fetch failed");
  return r.json();
}

export async function getEngagements(
  missionId: string,
  token: string
): Promise<Engagement[]> {
  const r = await authFetch(
    `${BASE}/missions/${encodeURIComponent(missionId)}/engagements`,
    token
  );
  if (!r.ok) throw new Error("engagements fetch failed");
  return r.json();
}
