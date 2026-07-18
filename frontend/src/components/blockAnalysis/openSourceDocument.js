import { API_BASE_URL } from "../../services/apiClient";

// Fetch the source document (FRA/FRAEW PDF) with auth and open it in a new tab.
// Uses a blob URL so the Authorization header is sent (a plain window.open of the
// URL wouldn't carry the token).
export async function openSourceDocument(uploadId, filename) {
  if (!uploadId) return;
  try {
    const token =
      localStorage.getItem("equirisk_token") || sessionStorage.getItem("equirisk_token");
    const res = await fetch(`${API_BASE_URL}/api/v1/upload/${uploadId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Could not load document (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    // Revoke after a delay so the new tab has time to load it.
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (err) {
    console.error("Failed to open source document:", err);
    alert(`Could not open ${filename || "the source document"}: ${err.message}`);
  }
}
