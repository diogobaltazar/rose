import type { AppConfig, Mission, Engagement, IntelDocument, IntelStats, IntelSearchResult } from "./types";

const BASE = "/api";

export async function getConfig(): Promise<AppConfig> {
  const r = await fetch(`${BASE}/config`);
  if (!r.ok) throw new Error("config fetch failed");
  return r.json();
}

async function authFetch(url: string, token: string, init?: RequestInit): Promise<Response> {
  return fetch(url, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...init?.headers },
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

export async function getIntelList(token: string): Promise<IntelDocument[]> {
  const r = await authFetch(`${BASE}/intel`, token);
  if (!r.ok) throw new Error("intel list fetch failed");
  return r.json();
}

export async function getIntelStats(token: string): Promise<IntelStats> {
  const r = await authFetch(`${BASE}/intel/stats`, token);
  if (!r.ok) throw new Error("intel stats fetch failed");
  return r.json();
}

export async function searchIntel(token: string, query: string): Promise<IntelSearchResult[]> {
  const r = await authFetch(`${BASE}/intel/search?q=${encodeURIComponent(query)}`, token);
  if (!r.ok) throw new Error("intel search failed");
  return r.json();
}

export async function createIntel(token: string, source: string, sourceUrl: string): Promise<IntelDocument> {
  const r = await authFetch(`${BASE}/intel`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, source_url: sourceUrl }),
  });
  if (!r.ok) throw new Error("intel create failed");
  return r.json();
}

export async function deleteIntel(token: string, uid: string): Promise<void> {
  const r = await authFetch(`${BASE}/intel/${uid}`, token, { method: "DELETE" });
  if (!r.ok) throw new Error("intel delete failed");
}
