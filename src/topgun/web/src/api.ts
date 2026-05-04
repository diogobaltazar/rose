import type { AppConfig, Mission, Engagement, IntelDocument, IntelStats, IntelSearchResult } from "./types";

const BASE = "/api";
const TTL = 5 * 60_000; // 5 minutes before a background refresh is triggered
const _cache = new Map<string, { ts: number; data: unknown }>();

function cached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const hit = _cache.get(key);
  if (hit) {
    if (Date.now() - hit.ts < TTL) return Promise.resolve(hit.data as T);
    // Stale — serve immediately, refresh silently in the background
    fn().then(data => _cache.set(key, { ts: Date.now(), data })).catch(() => {});
    return Promise.resolve(hit.data as T);
  }
  return fn().then(data => { _cache.set(key, { ts: Date.now(), data }); return data; });
}

export function invalidateCache(...keys: string[]) {
  if (keys.length === 0) _cache.clear();
  else keys.forEach(k => _cache.delete(k));
}

// Returns whatever is cached — stale or fresh. Used to initialise state
// synchronously so components never start with an empty screen.
export function peekCache<T>(key: string): T | null {
  const hit = _cache.get(key);
  return hit ? (hit.data as T) : null;
}

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
  return cached("missions", async () => {
    const r = await authFetch(`${BASE}/missions`, token);
    if (!r.ok) throw new Error("missions fetch failed");
    return r.json();
  });
}

export async function getEngagements(missionId: string, token: string): Promise<Engagement[]> {
  const r = await authFetch(`${BASE}/missions/${encodeURIComponent(missionId)}/engagements`, token);
  if (!r.ok) throw new Error("engagements fetch failed");
  return r.json();
}

export async function getIntelList(token: string): Promise<IntelDocument[]> {
  return cached("intel-list", async () => {
    const r = await authFetch(`${BASE}/intel`, token);
    if (!r.ok) throw new Error("intel list fetch failed");
    return r.json();
  });
}

export async function getIntelStats(token: string): Promise<IntelStats> {
  return cached("intel-stats", async () => {
    const r = await authFetch(`${BASE}/intel/stats`, token);
    if (!r.ok) throw new Error("intel stats fetch failed");
    return r.json();
  });
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
  invalidateCache("intel-list", "intel-stats");
  return r.json();
}

export async function deleteIntel(token: string, uid: string): Promise<void> {
  const r = await authFetch(`${BASE}/intel/${uid}`, token, { method: "DELETE" });
  if (!r.ok) throw new Error("intel delete failed");
  invalidateCache("intel-list", "intel-stats");
}

export async function tagAsMission(token: string, uid: string, sourceUrl: string): Promise<void> {
  const r = await authFetch(`${BASE}/intel/${uid}/mission`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_url: sourceUrl }),
  });
  if (!r.ok) throw new Error(`tag failed: ${await r.text()}`);
  invalidateCache("intel-list", "intel-stats");
}

export async function addGithubRepo(token: string, name: string, repo: string, pat: string): Promise<void> {
  const r = await authFetch(`${BASE}/connect/github/repo`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, repo, pat }),
  });
  if (!r.ok) throw new Error(`github repo connect failed: ${await r.text()}`);
  invalidateCache("intel-list", "intel-stats");
}

export async function removeGithubRepo(token: string, name: string): Promise<void> {
  const r = await authFetch(`${BASE}/connect/github/repo/${encodeURIComponent(name)}`, token, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error("github repo remove failed");
  invalidateCache("intel-list", "intel-stats");
}
