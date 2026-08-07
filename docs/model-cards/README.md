# Model cards

One per trained model version, auto-generated at training time. A model without a
card must not load — that is enforced in code from phase 5.

Each card records: data window, feature list with provenance flags, CV scheme,
metrics, class balance, parameter count, known limitations, and the training data
checksum.

Two standing entries you will need to write honestly:

- The propagation validator card must state that **no headline accuracy figure is
  reported**, and why: with this few real positives, such a number describes the
  synthetic injection process rather than the world.
- The HST-GAT card must justify its parameter count against the binding
  constraint — 720 hourly timesteps per station is a small corpus, and the
  architecture was sized for it deliberately.
