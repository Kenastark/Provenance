/**
 * The local operator-action queue.
 *
 * [Acknowledge] and [Dispatch] are stubs until phase 7 builds alerting, sign-off,
 * and RBAC. They write here - to this browser, and nowhere else.
 *
 * This is not a placeholder detail, it is the standing rule: no code path may
 * publish a public-facing alert without a recorded human sign-off. Until that
 * record exists there is deliberately no transport out of this module, and the UI
 * says plainly that a queued action has not left the browser. An operator must
 * never be able to believe they have warned the public when they have not.
 */

export type QueuedActionKind = "acknowledge" | "dispatch";

export interface QueuedAction {
  id: string;
  kind: QueuedActionKind;
  stationId: string;
  /** The reason codes visible on screen when the operator acted. */
  reasonCodes: string[];
  note: string;
  queuedAt: string;
}

const STORAGE_KEY = "provenance.action-queue";

type Listener = (actions: QueuedAction[]) => void;

const listeners = new Set<Listener>();
let cache: QueuedAction[] | null = null;

function read(): QueuedAction[] {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    cache = raw ? (JSON.parse(raw) as QueuedAction[]) : [];
  } catch {
    cache = [];
  }
  return cache;
}

function write(actions: QueuedAction[]): void {
  cache = actions;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(actions));
  } catch {
    // Storage being unavailable must not lose the action for this session; the
    // in-memory cache still holds it and the UI still reflects it.
  }
  for (const listener of listeners) listener(actions);
}

export function listQueuedActions(): QueuedAction[] {
  return [...read()];
}

export function queuedActionsFor(stationId: string): QueuedAction[] {
  return read().filter((action) => action.stationId === stationId);
}

export function queueAction(input: {
  kind: QueuedActionKind;
  stationId: string;
  reasonCodes?: string[];
  note?: string;
  now?: Date;
  id?: string;
}): QueuedAction {
  const action: QueuedAction = {
    id: input.id ?? `${input.kind}-${input.stationId}-${(input.now ?? new Date()).toISOString()}`,
    kind: input.kind,
    stationId: input.stationId,
    reasonCodes: input.reasonCodes ?? [],
    note: input.note ?? "",
    queuedAt: (input.now ?? new Date()).toISOString(),
  };
  write([action, ...read()]);
  return action;
}

export function clearQueue(): void {
  write([]);
}

export function subscribeToQueue(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Test-only: drop the memo so a fresh localStorage is picked up. */
export function resetQueueCache(): void {
  cache = null;
}

/**
 * The sentence shown beside a queued action. Phase 7 replaces the queue with a
 * real sign-off record; until then this text is the honest description of what
 * pressing the button did.
 */
export const QUEUE_DISCLOSURE =
  "Queued locally in this browser. Nothing has been sent: dispatch requires the human sign-off record that lands in phase 7.";
