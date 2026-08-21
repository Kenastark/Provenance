import type { ReactNode } from "react";
import { ApiError } from "../api/client";

/**
 * Loading, empty, and error states.
 *
 * Every panel in the dashboard has all three, designed rather than defaulted. The
 * error state in particular is a hard requirement of this phase's quality floor:
 * it says what happened and what to do, and it never says "Something went wrong".
 * When the failure came from the API we already have both halves - the RFC 7807
 * `detail` is what happened, and `ApiError.remedy` is what to do - plus a request
 * id an operator can quote.
 */

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div
      className="flex items-center gap-3 p-5 text-body text-text-tertiary"
      role="status"
      aria-live="polite"
      data-testid="loading-state"
    >
      <span
        aria-hidden="true"
        className="h-3 w-3 animate-pulse rounded-full bg-text-tertiary"
      />
      {label}…
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="p-5 text-body" data-testid="empty-state">
      <p className="font-display text-subhead text-text">{title}</p>
      <p className="mt-2 max-w-full text-text-secondary">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  error,
  what,
  onRetry,
}: {
  error: unknown;
  /** What the app was trying to do, e.g. "load the station list". */
  what: string;
  onRetry?: () => void;
}) {
  const api = error instanceof ApiError ? error : null;
  const happened = api
    ? api.detail
    : error instanceof Error
      ? error.message
      : `An unexpected failure occurred while trying to ${what}.`;
  const remedy = api
    ? api.remedy
    : "Reload the page. If it keeps failing, check the browser console and the API logs.";

  return (
    <div className="p-5 text-body" role="alert" data-testid="error-state">
      <p className="font-display text-subhead prov-state-fault">Could not {what}</p>
      <p className="mt-2 text-text">{happened}</p>
      <p className="mt-1 text-text-secondary">{remedy}</p>
      {api?.requestId && (
        <p className="mt-2 font-mono text-caption text-text-tertiary">
          Request id: {api.requestId}
        </p>
      )}
      {onRetry && (
        <button type="button" className="prov-button mt-4" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/**
 * The slot for something a later phase computes.
 *
 * SHAP and graph attention fall back to one of these whenever their model artefact is
 * absent (never trained, or trained on data the current drop does not carry), rather
 * than being hidden. Showing the empty slot is a small honesty: the operator learns the
 * shape of the finished product, and nobody is tempted to fake a verdict in the meantime.
 */
export function NotYetComputed({ title, arrivesIn }: { title: string; arrivesIn: string }) {
  return (
    <div
      className="prov-panel border-dashed p-4 text-body text-text-tertiary"
      data-testid="not-yet-computed"
    >
      <p className="text-text-secondary">{title}</p>
      <p className="mt-1 text-caption">Not yet computed — {arrivesIn}.</p>
    </div>
  );
}
