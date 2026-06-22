const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Station {
  id: string;
  name: string;
}

export interface ScheduleEntry {
  platform: string;
  platform_id: string;
  operator: string;
  departure_time: string;
  arrival_time: string;
  bus_type: string;
  fare: number | null;
  booking_url: string;
  route_number: string | null;
}

export interface RouteResult {
  id: number;
  origin: string;
  destination: string;
  schedules: ScheduleEntry[];
  platform_count: number;
  bus_count: number;
}

export interface SearchResponse {
  from_station: string;
  to_station: string;
  routes: RouteResult[];
  total_buses: number;
  platforms: string[];
}

export interface RouteListItem {
  id: number;
  origin: string;
  destination: string;
  bus_count: number;
}

export interface Platform {
  id: string;
  name: string;
  url: string;
}

export interface Health {
  status: string;
  platforms: number;
  routes: number;
  schedules: number;
}

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    if (res.status === 404) return null as T;
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}

export async function searchBuses(from: string, to: string): Promise<SearchResponse | null> {
  return fetchAPI<SearchResponse>(
    `/api/search?from_station=${encodeURIComponent(from)}&to_station=${encodeURIComponent(to)}`
  );
}

export async function getStations(q: string = ""): Promise<Station[]> {
  const params = q ? `?q=${encodeURIComponent(q)}&limit=20` : "?limit=50";
  return fetchAPI<Station[]>(`/api/stations${params}`) as Promise<Station[]>;
}

export async function getRoutes(limit = 50): Promise<RouteListItem[]> {
  return fetchAPI<RouteListItem[]>(`/api/routes?limit=${limit}`) as Promise<RouteListItem[]>;
}

export async function getRoute(id: number): Promise<RouteResult | null> {
  return fetchAPI<RouteResult>(`/api/routes/${id}`);
}

export async function getPlatforms(): Promise<Platform[]> {
  return fetchAPI<Platform[]>(`/api/platforms`) as Promise<Platform[]>;
}

export async function getHealth(): Promise<Health> {
  return fetchAPI<Health>("/api/health");
}
