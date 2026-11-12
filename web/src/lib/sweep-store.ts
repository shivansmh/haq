import { useSyncExternalStore } from "react";
import type { SweepResult } from "./haq-types";

export type Activity = { at: string; text: string };
type State = { result: SweepResult | null; activity: Activity[] };
const KEY = "haq-sweep-state";
let state: State = { result: null, activity: [] };
let loaded = false;
const subs = new Set<() => void>();

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try { const raw = sessionStorage.getItem(KEY); if (raw) state = JSON.parse(raw); } catch { /* ignore */ }
}
function emit() { try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch { /* ignore */ } subs.forEach((f) => f()); }
const empty: State = { result: null, activity: [] };

export const sweepStore = {
  setResult(result: SweepResult) { load(); state = { ...state, result }; emit(); },
  log(text: string) { load(); state = { ...state, activity: [{ at: new Date().toISOString(), text }, ...state.activity].slice(0, 50) }; emit(); },
  clear() { state = { result: null, activity: state.activity }; emit(); },
};

export function useSweepState(): State {
  return useSyncExternalStore(
    (cb) => { load(); subs.add(cb); cb(); return () => subs.delete(cb); },
    () => { load(); return state; },
    () => empty,
  );
}
