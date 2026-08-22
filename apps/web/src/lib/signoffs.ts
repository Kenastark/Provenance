import type { SignoffRecord } from "../api/operations";
import { toDate } from "./format";

/**
 * A browser-local mirror of sign-off records this session has created.
 *
 * The record itself lives server-side the moment `POST /v1/decision/signoff`
 * returns - this module never invents one, and it is not the thing that blocks a
 * dispatch. `gate.dispatch` re-validates the sign-off against the database on
 * every call (see `test_signoff_gate.py`), so a stale or cleared local cache can
 * only make the dispatch button *more* cautious than the server, never less: the
 * worst this cache can do wrong is ask an operator to sign off again when a valid
 * record already exists. What it buys is continuity - the sign-off panel still
 * shows "who, when, which channel" after a reload during a demo.
 */

const STORAGE_KEY = "provenance.signoffs";

type Listener = (records: SignoffRecord[]) => void;

const listeners = new Set<Listener>();
let cache: SignoffRecord[] | null = null;

function read(): SignoffRecord[] {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    cache = raw ? (JSON.parse(raw) as SignoffRecord[]) : [];
  } catch {
    cache = [];
  }
  return cache;
}

function write(records: SignoffRecord[]): void {
  cache = records;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
  } catch {
    // Storage being unavailable must not lose the record for this session; the
    // in-memory cache still holds it and the panel still reflects it.
  }
  for (const listener of listeners) listener(records);
}

/** Newest first, for one event. */
export function signoffsForEvent(eventId: number): SignoffRecord[] {
  return read()
    .filter((record) => record.event_id === eventId)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}

export function rememberSignoff(record: SignoffRecord): void {
  write([record, ...read().filter((existing) => existing.signoff_id !== record.signoff_id)]);
}

export function subscribeToSignoffs(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Test-only: drop the memo so a fresh localStorage is picked up. */
export function resetSignoffCache(): void {
  cache = null;
}

/** A sign-off authorises a dispatch only for its own channel and only before it
 * expires - the same two conditions `validate_signoff` checks server-side.
 *
 * `expires_at` is a naive-UTC string like every other timestamp this API emits
 * (`format.ts`'s `parseUtc` explains why) - a bare `new Date(expires_at)` reads it
 * as *local* time instead, which is wrong by the browser's UTC offset. In a
 * timezone ahead of UTC that silently misreads a still-valid sign-off as already
 * expired, since the shifted instant is earlier. `toDate` is the same UTC-safe
 * parser every other timestamp in the dashboard goes through. */
export function isSignoffUsable(
  record: SignoffRecord,
  channel: string,
  now: Date = new Date(),
): boolean {
  const expiresAt = toDate(record.expires_at);
  return record.channel === channel && expiresAt !== null && expiresAt.getTime() > now.getTime();
}
