# 3-minute video storyboard (v1.2)

Version 1.2. **Supersedes `video-storyboard-v1.1-real-data.md`** (untouched, per standing
rule 10). Target runtime **3:00**. Fully offline to record (`make demo-record`).

**Changed from v1.1:** shot 1's on-screen product descriptor only — "AI Trust Layer for
Environmental Data" → **"An AI trust layer for Environmental Sensor Networks."**, matching
`CLAUDE.md`'s updated definition. No other shot, figure, or verdict changed; see v1.1 for
that derivation (`docs/updates/u22-headline-reconciliation.md`).

| # | Time | Shot | On screen | Voiceover (VO) |
|---|------|------|-----------|----------------|
| 1 | 0:00–0:20 | Title | Mark + "An AI trust layer for Environmental Sensor Networks." + "Is This Real?" | "A number on a screen looks the same whether it's true or broken. This is how you tell the difference." |
| 2 | 0:20–0:45 | Network map + KPIs | 149,683 readings · 100.00% conventional completeness · 16 stations, all green | "Debrecen's environmental network. Every row it delivered carries a value. By every conventional measure, perfectly healthy." |
| 3 | 0:45–1:10 | Defect ledger fills in | Defect rate 29.1% of 174,583 owed readings; R01/R12/R10/R13/R11 counts appear | "It isn't. Twenty-nine per cent of the readings it owed us are absent or wrong. Half never arrived. The other half arrived, look fine, and are wrong." |
| 4 | 1:10–1:25 | By-station panel + structural-exclusion row | Per-station rates 18–40%; a 'coverage fact', greyed, excluded from the rate | "Not one broken sensor — every station between eighteen and forty per cent. And a sensor a station never carried isn't a fault at all. We exclude it, and a test makes sure we always do." |
| 5 | 1:25–2:00 | Zoom to KER11; wind graph overlay | PM10 4,100.7 µg/m³; trust 0.73 → 0.43; code T04; five downwind neighbours queried | "KER11 reports 4,100 micrograms — the only physically impossible reading in the whole corpus. Trust collapses, deterministically. Real plume, or broken sensor? Ask the neighbours downwind." |
| 6 | 2:00–2:20 | Verdict card + the routed-to-review contrast | Verdict: LIKELY_FAULT, high confidence; nine sibling events showing AMBIGUOUS → routed to review | "A plume should have raised them by two thousand micrograms. They saw nought point one six eight. Likely fault — and it's the only one of ten the system was willing to call. The other nine went to a human." |
| 7 | 2:20–2:40 | Raw vs deweathered series | Spike shrinks after deweathering; a genuine fault stays lit | "Strip the weather, score the residual. The inversion falls away; the real fault stays." |
| 8 | 2:40–2:55 | Trust score card | Component breakdown + reason codes visible; a 'degraded' badge shown | "Every score carries its reasons. Miss a model? It degrades to statistics and says so — it never goes dark." |
| 9 | 2:55–3:00 | Title card | "Is This Real?" | "Now you can answer." |

## Production notes

- **Capture:** `make demo-record` writes `reports/demo/*.json` (the deterministic replay
  sequences) and, if a recorder is present, `reports/demo/demo.mp4`. The JSON is the
  fallback if screen capture is unavailable.
- **Numbers:** shots 2–6 show the **real export** figures (`data/raw`, checksum
  `8f8efeedfabdccaa`). Recording against the offline synthetic corpus changes the digits
  **and shot 6's verdict** — the synthetic top event adjudicates AMBIGUOUS. Re-cut the VO
  for shot 6 rather than reading the real-drop line over synthetic footage.
- **Station count:** shot 2 says 16 stations, matching the audit's own `n_stations`. v1.0
  said "18 monitoring points", counting the two surface-water points separately as
  `CLAUDE.md` does. Both framings are defensible; pick one and use it in every asset.
- **Never re-key a number by hand** — read it from the replay sequence.
- **No live network.** Basemap tiles are vendored for the Debrecen bbox; with none, the
  map uses the token-coloured ground and the video still tells the whole story.
- **Tone:** calm, operator-facing, evidence-first. No accuracy claims for the propagation
  validator (standing rule 4) — show the per-case evidence, not a score.
