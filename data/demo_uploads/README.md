# Demo uploads

These contracts are excluded from the pre-loaded dataset intentionally. Upload them via the app's upload button to demonstrate live analysis.

| File | What the review should catch |
|---|---|
| `2026-09-18_gulf_crown_hotels_msa_draft.md` | Conflicts with the Al Noor non-compete in the commitment register |
| `2026-09-10_harrington_health_msa_draft.md` | Healthcare deal with no signed BAA and no subcontractor BAA (HIPAA gap) |

The app only scans `data/incoming/`, so nothing in this folder appears in the draft list, queue or offline demo. The tests read these files directly from here.
