# Documentation

| Directory | What lives here |
|---|---|
| `decisions/` | ADRs. Numbered, immutable once merged. Supersede rather than edit. |
| `model-cards/` | One per trained model version. A model without a card must not load. |
| `api/` | API reference and worked examples. |
| `demo/` | The competition demo script, judge Q&A prep, and submission materials. |

## Versioning

Documents follow `name-vX.Y-descriptor.md` and are **never edited in place**. A
revision is a new file with an incremented version and a header saying what it
supersedes. The full revision history stays readable without going through git.

This matters more than it sounds: the blueprint, the demo script, and the model
cards are all things a judge may ask to see the evolution of.
