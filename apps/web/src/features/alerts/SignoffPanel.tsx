import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";
import { useCreateSignoff, useDispatchAlert } from "../../api/queries";
import { ApiError } from "../../api/client";
import { SIGNOFF_CHANNELS, type SignoffChannel } from "../../api/operations";
import { formatTimestamp } from "../../lib/format";
import {
  isSignoffUsable,
  rememberSignoff,
  signoffsForEvent,
  subscribeToSignoffs,
} from "../../lib/signoffs";

/**
 * The sign-off gate, rendered.
 *
 * This is the frontend half of standing rule 5: *no code path may publish a
 * public-facing alert without a recorded human sign-off*. The backend half is the
 * static call-graph proof in `test_signoff_gate.py` - `gate.dispatch` refuses to
 * send without calling `validate_signoff` first, and nothing else in the codebase
 * can reach a channel sender. This panel cannot weaken that: it can only make the
 * already-enforced block legible, by disabling the dispatch action and stating in
 * one sentence why, until a valid sign-off for the chosen channel exists. Even if
 * this component had a bug, the request still 422s server-side.
 */

const CHANNEL_LABEL: Record<SignoffChannel, string> = {
  webhook: "Webhook",
  email: "Email",
  sms: "SMS",
};

export function SignoffPanel({
  eventId,
  defaultOperator,
}: {
  eventId: number;
  defaultOperator: string;
}) {
  const [channel, setChannel] = useState<SignoffChannel>("webhook");
  const [operator, setOperator] = useState(defaultOperator);
  const [known, setKnown] = useState(() => signoffsForEvent(eventId));
  const blockedId = useId();

  useEffect(() => setKnown(signoffsForEvent(eventId)), [eventId]);
  useEffect(() => subscribeToSignoffs(() => setKnown(signoffsForEvent(eventId))), [eventId]);
  // A newly selected alert's operator field should reset to the default, not carry
  // over whatever the previous alert's box held.
  useEffect(() => setOperator(defaultOperator), [eventId, defaultOperator]);

  const signoff = useCreateSignoff();
  const dispatch = useDispatchAlert();

  const usable = known.find((record) => isSignoffUsable(record, channel));
  const dispatchBlocked = !usable;

  const onSignoff = (event: FormEvent) => {
    event.preventDefault();
    signoff.mutate(
      { event_id: eventId, channel, operator: operator.trim() || "operator" },
      {
        onSuccess: (record) => {
          rememberSignoff(record);
          dispatch.reset();
        },
      },
    );
  };

  const onDispatch = () => {
    if (!usable) return;
    dispatch.mutate({ event_id: eventId, channel, signoff_id: usable.signoff_id });
  };

  return (
    <div className="flex flex-col gap-4" data-testid="signoff-panel">
      {/* --------------------------------------------------------- sign-off */}
      <form className="flex flex-wrap items-end gap-3" onSubmit={onSignoff}>
        <label className="flex flex-col gap-1 text-caption text-text-tertiary">
          <span>Channel</span>
          <select
            className="prov-input"
            value={channel}
            onChange={(event) => setChannel(event.target.value as SignoffChannel)}
            data-testid="signoff-channel"
          >
            {SIGNOFF_CHANNELS.map((option) => (
              <option key={option} value={option}>
                {CHANNEL_LABEL[option]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-caption text-text-tertiary">
          <span>Operator</span>
          <input
            className="prov-input"
            value={operator}
            onChange={(event) => setOperator(event.target.value)}
            data-testid="signoff-operator"
            required
          />
        </label>
        <button type="submit" className="prov-button" disabled={signoff.isPending}>
          {signoff.isPending ? "Recording…" : "Record sign-off"}
        </button>
      </form>
      <p className="text-caption text-text-tertiary">
        Recording a sign-off does not send anything. It captures who is signing off, the exact
        evidence they saw, and a 15-minute window in which they may then dispatch.
      </p>
      {signoff.isError && (
        <p className="text-caption prov-state-fault" role="alert" data-testid="signoff-error">
          {signoff.error instanceof ApiError
            ? signoff.error.detail
            : "The sign-off could not be recorded."}
        </p>
      )}

      {known.length > 0 && (
        <ul className="m-0 list-none space-y-1 p-0 text-caption" data-testid="signoff-records">
          {known.map((record) => {
            const usableNow = isSignoffUsable(record, record.channel);
            return (
              <li key={record.signoff_id} className="flex flex-wrap items-center gap-2">
                <span className={usableNow ? "prov-state-verified" : "text-text-tertiary"}>
                  {usableNow ? "valid" : "expired"}
                </span>
                <span className="text-text">
                  {CHANNEL_LABEL[record.channel]} · signed off by {record.operator} at{" "}
                  {formatTimestamp(record.created_at)}, expires {formatTimestamp(record.expires_at)}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {/* --------------------------------------------------------- dispatch */}
      <div className="border-t border-border pt-3">
        <button
          type="button"
          className="prov-button prov-button--primary"
          onClick={onDispatch}
          disabled={dispatchBlocked || dispatch.isPending}
          aria-describedby={dispatchBlocked ? blockedId : undefined}
          data-testid="dispatch-button"
        >
          {dispatch.isPending ? "Dispatching…" : `Dispatch via ${CHANNEL_LABEL[channel]}`}
        </button>
        {dispatchBlocked && (
          <p id={blockedId} className="mt-2 text-caption prov-state-degraded" data-testid="dispatch-blocked">
            Dispatch is blocked: there is no valid, unexpired sign-off for this event on{" "}
            {CHANNEL_LABEL[channel]} yet. Record a sign-off above first.
          </p>
        )}
        {dispatch.isError && (
          <p className="mt-2 text-caption prov-state-fault" role="alert" data-testid="dispatch-error">
            {dispatch.error instanceof ApiError
              ? dispatch.error.detail
              : "The dispatch could not be completed."}
          </p>
        )}
        {dispatch.isSuccess && (
          <p className="mt-2 text-caption prov-state-verified" role="status" data-testid="dispatch-success">
            {dispatch.data.idempotent
              ? "Already dispatched — this replayed the existing record rather than sending again."
              : "Dispatched."}{" "}
            Status {dispatch.data.status}, dispatch id {dispatch.data.dispatch_id}.
          </p>
        )}
      </div>
    </div>
  );
}
