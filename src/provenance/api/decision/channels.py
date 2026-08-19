"""The low-level dispatch primitives — the only functions that actually "send".

These are deliberately the narrowest possible surface, and they are reachable from
exactly one place: the sign-off gate (:mod:`provenance.api.decision.gate`). A static
architecture test enforces that — if any other module ever calls one of these, the
test fails, because that would be a path to a public alert that skipped the human
sign-off (standing rule 5).

**Offline by construction.** This build performs no network egress: a "send" appends
a receipt to a local outbox and returns it. That is what lets the whole demo and the
test suite run with the network blocked (the offline test asserts it). A production
deployment injects a real transport at the ``deliver`` boundary; the gate and its
guarantees are unchanged by that swap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# The local outbox: what *would* have been sent. Inspectable for the demo and the
# audit trail; never a network call.
OUTBOX: list[dict[str, Any]] = []

CHANNELS: frozenset[str] = frozenset({"webhook", "email", "sms"})


def _receipt(channel: str, payload: dict[str, Any]) -> dict[str, Any]:
    receipt = {
        "channel": channel,
        "delivered_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        "idempotency_key": payload.get("idempotency_key"),
        "event_id": payload.get("event_id"),
        "signoff_id": payload.get("signoff_id"),
    }
    OUTBOX.append(receipt)
    return receipt


def send_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    return _receipt("webhook", payload)


def send_email(payload: dict[str, Any]) -> dict[str, Any]:
    return _receipt("email", payload)


def send_sms(payload: dict[str, Any]) -> dict[str, Any]:
    return _receipt("sms", payload)


_SENDERS = {"webhook": send_webhook, "email": send_email, "sms": send_sms}


def deliver(channel: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Route a validated dispatch to its channel sender. Called only by the gate."""
    sender = _SENDERS.get(channel)
    if sender is None:
        raise ValueError(
            f"Unknown dispatch channel {channel!r}; expected one of {sorted(CHANNELS)}."
        )
    return sender(payload)
