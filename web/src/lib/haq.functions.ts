import fixture from "./demo-sweep.json";
import { API_BASE, type SweepResult } from "./haq-types";

const BASE = API_BASE;
const DEMO_SESSION_KEY = "haq-demo-session";

function demoSessionId(): string {
  try {
    let id = sessionStorage.getItem(DEMO_SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem(DEMO_SESSION_KEY, id);
    }
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

/** Runs the sample-inbox sweep on the Haq API; falls back to a bundled copy if the API is asleep. */
export async function runDemoSweep(): Promise<SweepResult & { source: "live-api" | "bundled" }> {
  try {
    const res = await fetch(`${BASE}/v1/gmail/demo`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Haq-Demo-Session": demoSessionId(),
      },
      signal: AbortSignal.timeout(20000),
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return { ...((await res.json()) as SweepResult), source: "live-api" };
  } catch (e) {
    console.error("Demo sweep API unavailable, using bundled sample", e);
    return { ...(fixture as unknown as SweepResult), source: "bundled" };
  }
}

export type Classification = {
  category: "failed_payment" | "msme_dues" | "unclaimed_wealth" | "general_rights";
  confidence: number;
  title: string;
  summary: string;
  statutory_law: string;
  suggested_route: string;
  extracted_entities: Record<string, string | number | boolean | null>;
};

/** Sends a plain-language description of the problem to the Haq API to identify which right applies. */
export async function classifyClaim(data: { prompt: string }): Promise<Classification> {
  const prompt = String(data?.prompt ?? "").trim();
  if (prompt.length < 10 || prompt.length > 4000) throw new Error("Please describe the problem in 10–4000 characters.");
  const res = await fetch(`${BASE}/v1/classify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }), signal: AbortSignal.timeout(30000) });
  if (!res.ok) throw new Error(`The Haq service couldn't read this (${res.status}). It may be waking up — try again in a moment.`);
  return (await res.json()) as Classification;
}
