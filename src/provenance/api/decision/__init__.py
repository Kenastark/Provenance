"""The human sign-off gate for public-facing dispatch (§4, §16 critique 5).

Standing rule 5 and Never-do #8: *no code path may publish a public-facing alert
without a human sign-off record.* This package makes that mechanical. Every real
dispatch — webhook, email, SMS — passes through exactly one choke point,
:func:`provenance.api.decision.gate.dispatch`, which refuses to deliver without a
valid, non-expired operator sign-off, and records the send idempotently so a retry
never double-sends.

``tests/architecture/test_signoff_gate.py`` proves it statically: the channel senders
are reachable from nowhere but the gate, and the gate validates a sign-off before it
ever calls one. This is the ethical commitment made into a call-graph invariant.
"""
