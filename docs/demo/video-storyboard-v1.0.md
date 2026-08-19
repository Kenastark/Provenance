# 3-minute video storyboard (v1.0)

Version 1.0. Supersedes nothing; first version. Target runtime **3:00**. Fully offline
to record (`make demo-record`); the replay sequences under `reports/demo/*.json` are the
byte-exact source of every on-screen number.

| # | Time | Shot | On screen | Voiceover (VO) |
|---|------|------|-----------|----------------|
| 1 | 0:00–0:20 | Title | Mark + "AI Trust Layer for Environmental Data" + "Is This Real?" | "A number on a screen looks the same whether it's true or broken. This is how you tell the difference." |
| 2 | 0:20–0:45 | Network map + KPIs | 149,683 readings · 99.95% complete · 18 monitoring points, all green | "Debrecen's environmental network. By every conventional measure, perfectly healthy." |
| 3 | 0:45–1:10 | Defect ledger fills in | Frozen-sensor (R12) and detection-limit (R11) flags appear; defect rate ticks up | "It isn't. Sensors frozen on one value. Readings pinned at a limit. Impossible spikes. Nothing missing — everything present, and wrong." |
| 4 | 1:10–1:25 | Structural-exclusion row highlighted | A 'coverage fact', greyed, excluded from the rate | "A sensor a station never carried isn't a fault. We exclude it from the rate — and a test makes sure we always do." |
| 5 | 1:25–2:00 | Zoom to KER11; wind graph overlay | PM10 4,100.7 µg/m³; trust 0.577 → 0.275; code T04; downwind neighbours queried | "KER11 reports 4,100 micrograms. Trust collapses — physically impossible, deterministically. Real plume, or broken sensor? Ask the neighbours downwind." |
| 6 | 2:00–2:20 | Verdict card + sign-off gate | Verdict: AMBIGUOUS → routed to human review; sign-off dialog | "No corroboration downwind. So we don't guess — we route it to a human. And nothing reaches the public without a recorded sign-off." |
| 7 | 2:20–2:40 | Raw vs deweathered series | Spike shrinks after deweathering; a genuine fault stays lit | "Strip the weather, score the residual. The inversion falls away; the real fault stays." |
| 8 | 2:40–2:55 | Trust score card | Component breakdown + reason codes visible; a 'degraded' badge shown | "Every score carries its reasons. Miss a model? It degrades to statistics and says so — it never goes dark." |
| 9 | 2:55–3:00 | Title card | "Is This Real?" | "Now you can answer." |

## Production notes

- **Capture:** `make demo-record` writes `reports/demo/*.json` (the deterministic replay
  sequences) and, if a recorder is present, `reports/demo/demo.mp4`. The JSON is the
  fallback if screen capture is unavailable.
- **Numbers:** shots 2–3 and 5 show the **real export** figures; if recording against the
  offline synthetic corpus, the digits differ (75,585 readings, ~2.9% defect rate, top
  event ~3,000 µg/m³ → AMBIGUOUS) but every beat is identical. Never re-key a number by
  hand — read it from the replay sequence.
- **No live network.** Basemap tiles are vendored for the Debrecen bbox; with none, the
  map uses the token-coloured ground and the video still tells the whole story.
- **Tone:** calm, operator-facing, evidence-first. No accuracy claims for the propagation
  validator (standing rule 4) — show the per-case evidence, not a score.
