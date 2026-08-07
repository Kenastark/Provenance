# API

Phase 2 fills this in with the OpenAPI reference and worked `curl` examples.

Three consumers, three shapes:

- **Operators** — the dashboard, over REST + WebSocket.
- **Researchers and agencies** — REST, with both raw and quality-flagged series
  and uncertainty bounds, plus the audit-trail export.
- **Emergency services** — a webhook feed that only fires after an event clears
  propagation validation *and* a human has signed off.

Every trust score in every response carries its component breakdown and at least
one reason code. There is no endpoint that returns a bare number.
