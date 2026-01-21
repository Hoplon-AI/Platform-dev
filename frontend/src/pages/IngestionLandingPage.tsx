import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiFetch } from "../services/apiClient";

type Submission = {
  upload_id: string;
  ha_id: string;
  filename: string;
  file_type: string;
  status: string;
  uploaded_at: string;
  file_size: number;
  checksum: string;
  metadata?: unknown;
};

type ListResponse = {
  items: Submission[];
};

type BatchUploadResponse = {
  total_files: number;
  successful: number;
  failed: number;
  results: Array<{
    upload_id: string;
    filename: string;
    file_type: string;
    s3_key: string;
    manifest_s3_key?: string | null;
    metadata_s3_key?: string | null;
    checksum: string;
    file_size: number;
  }>;
  errors: Array<{ filename: string; error: string; error_type?: string }>;
};

function formatDateTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function formatBytes(n: number) {
  if (!Number.isFinite(n)) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function IngestionLandingPage() {
  const [items, setItems] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<BatchUploadResponse | null>(
    null,
  );

  const sorted = useMemo(() => {
    return [...items].sort(
      (a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime(),
    );
  }, [items]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/upload/submissions?limit=50");
      const data = (await res.json()) as ListResponse;
      setItems(data.items ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadResult(null);
    setError(null);
    try {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append("files", f));
      const res = await apiFetch("/api/v1/upload/batch", {
        method: "POST",
        body: form,
      });
      const data = (await res.json()) as BatchUploadResponse;
      setUploadResult(data);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28 }}>Ingestion</h1>
          <div className="subtle" style={{ marginTop: 6 }}>
            Upload files (batch) and browse recent submissions.
          </div>
        </div>
        <div className="row" style={{ alignItems: "center" }}>
          <Link className="btn" to="/portfolio">
            Go to PortfolioOverview
          </Link>
          <button className="btn" type="button" onClick={refresh} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Upload</h3>
        <div className="subtle" style={{ marginBottom: 10 }}>
          Uses <code>/api/v1/upload/batch</code> (auto-detects file type).
        </div>
        <input
          type="file"
          multiple
          onChange={(e) => void onUpload(e.target.files)}
          disabled={uploading}
        />
        {uploading ? <div className="subtle" style={{ marginTop: 10 }}>Uploading…</div> : null}

        {uploadResult ? (
          <div style={{ marginTop: 12 }}>
            <div className="subtle">
              Uploaded: {uploadResult.successful}/{uploadResult.total_files} · Failed:{" "}
              {uploadResult.failed}
            </div>
            {uploadResult.errors?.length ? (
              <div className="subtle" style={{ marginTop: 8 }}>
                Errors:
                <ul>
                  {uploadResult.errors.map((e, idx) => (
                    <li key={idx}>
                      {e.filename}: {e.error}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="card" style={{ marginTop: 16, borderColor: "#ef4444" }}>
          <h3>Error</h3>
          <div style={{ whiteSpace: "pre-wrap" }}>{error}</div>
        </div>
      ) : null}

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Recent submissions</h3>
        {loading ? (
          <div className="subtle">Loading…</div>
        ) : sorted.length === 0 ? (
          <div className="subtle">No submissions yet.</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            {sorted.map((s) => (
              <div
                key={s.upload_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  gap: 8,
                  padding: "10px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  background: "rgba(2, 6, 23, 0.35)",
                }}
              >
                <div style={{ display: "grid", gap: 2 }}>
                  <div style={{ fontWeight: 600 }}>
                    {s.file_type} — {s.filename}
                  </div>
                  <div className="subtle">
                    {s.status} · {s.file_type} · {s.ha_id} · {formatBytes(s.file_size)}
                  </div>
                  <div className="subtle" style={{ fontFamily: "monospace" }}>
                    {s.upload_id}
                  </div>
                </div>
                <div className="subtle" style={{ whiteSpace: "nowrap" }}>
                  {formatDateTime(s.uploaded_at)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

