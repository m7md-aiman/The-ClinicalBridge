import type {
  EvaluationReport,
  Meta,
  ResultPayload,
  ScenarioSummary,
} from "@/lib/types";

// Resolve the API base at runtime so the static export is host-agnostic:
// - explicit NEXT_PUBLIC_API_BASE wins (if set at build time);
// - `next dev` on :3000 -> talk to the FastAPI dev server on :8000;
// - otherwise same-origin (the export is served by FastAPI) -> relative "".
function resolveApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_BASE;
  if (env) return env;
  if (typeof window !== "undefined" && window.location.port === "3000") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "";
}

export const API_BASE = resolveApiBase();

// Read helper: try the live backend first (local dev / FastAPI-served prod), then fall back to a
// bundled static snapshot under /data (the pure-static Vercel deploy, which has no backend).
async function getJSON<T>(apiPath: string, staticPath: string): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${apiPath}`, { cache: "no-store" });
    if (res.ok) return (await res.json()) as T;
  } catch {
    /* no backend reachable — fall back to the static snapshot */
  }
  const res = await fetch(staticPath, { cache: "no-store" });
  if (!res.ok) throw new Error(`${apiPath} / ${staticPath} -> ${res.status}`);
  return (await res.json()) as T;
}

export const getMeta = () => getJSON<Meta>("/api/meta", "/data/meta.json");
export const getScenarios = () => getJSON<ScenarioSummary[]>("/api/scenarios", "/data/scenarios.json");
export const getResult = (id: string) =>
  getJSON<ResultPayload>(`/api/results/${id}`, `/data/results/${id}.json`);
export const getEvaluation = () => getJSON<EvaluationReport>("/api/evaluation", "/data/evaluation.json");

export interface StreamHandlers {
  onStep: (step: string, summary: string, data: Record<string, unknown>) => void;
  onResult: (result: unknown) => void;
  onError: (message: string) => void;
}

/** Open an SSE stream for a live pipeline run. Returns a cleanup function. */
export function streamRun(scenarioId: string, handlers: StreamHandlers): () => void {
  const es = new EventSource(`${API_BASE}/api/run/stream?scenario=${encodeURIComponent(scenarioId)}`);

  es.addEventListener("step", (e) => {
    const d = JSON.parse((e as MessageEvent).data);
    handlers.onStep(d.step, d.summary, d.data ?? {});
  });
  es.addEventListener("result", (e) => {
    const d = JSON.parse((e as MessageEvent).data);
    handlers.onResult(d.result);
    es.close();
  });
  es.addEventListener("error", (e) => {
    const msg = (e as MessageEvent).data
      ? JSON.parse((e as MessageEvent).data).message
      : "stream error";
    handlers.onError(msg);
    es.close();
  });

  return () => es.close();
}
