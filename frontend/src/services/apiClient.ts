export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function getAuthHeader(): Record<string, string> {
  const token =
    localStorage.getItem("equirisk_token") ||
    sessionStorage.getItem("equirisk_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch(path: string, init?: RequestInit) {
  const url = new URL(path, API_BASE_URL).toString();

  // Avoid triggering CORS preflight on simple GETs by only setting Content-Type
  // when we actually send JSON. For FormData, the browser sets the boundary.
  const body = init?.body;
  const isFormData =
    typeof FormData !== "undefined" && body instanceof FormData;
  const isJsonBody = body != null && !isFormData;

  const res = await fetch(url, {
    ...init,
    headers: {
      ...(isJsonBody ? { "Content-Type": "application/json" } : {}),
      ...getAuthHeader(),
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res;
}

