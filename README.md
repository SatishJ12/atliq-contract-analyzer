# AtliQ Contract Risk Analyzer — working prototype (Deliverable 5)

A Streamlit app that tells AtliQ's CEO, before he signs, what a contract really commits AtliQ to: risky clauses against his own playbook, the wrong entity or governing law, conflicts with obligations AtliQ has **already signed**, missing documents (BAA, DPA, subcontractor BAAs), and unfair terms when AtliQ is the buyer.

Built on the synthetic AtliQ dataset (dataset "today" = 28 Sep 2026). Not legal advice.

## What it does

| Feature (PRD ref) | How it works | Needs API key? |
|---|---|---|
| **Commitment register** (F1) | 12 obligations extracted from the 17 signed contracts, each with a verbatim quote, who it binds, and when it ends (`commitment_register.json`). `build_register.py` shows how Claude re-extracts it. | No |
| **Conflict check** (F2) | Register rules (Al Noor GCC non-compete, Crestline MFN rate floor, Northwind PipeKit assignment, CloudSpan exclusivity, HIPAA BAA scope) plus TF-IDF retrieval of the closest clauses AtliQ has already signed. | No |
| **Clause risk scan** (F3) | Karandeep's checklist as code: LDs, liability, indemnity, payment, IP, termination, NDAs, insurance. Every finding quotes the clause. | No |
| **Entity & governing law** (F4) | AtliQ Inc for US clients, Pvt Ltd for everyone else (`atliq_entities.md`); invoicing-entity mismatch; India template sent to a US party. | No |
| **Document-set completeness** (F5) | PHI → NDA + MSA + signed BAA + subcontractor BAAs; GDPR → DPA + SCCs; annexes referenced but not attached. | No |
| **Fairness check** (F6) | When AtliQ is the buyer, the same rules are applied from the vendor's side and labelled "Fairness". | No |
| **Review brief + decision log** (F7) | Per-finding decision (Negotiate / Accept risk / Escalate) with a note; downloadable brief (.md) and log (.json). Escalation to counsel suggested per PRD rules. | No |
| **Claude review** | `claude-sonnet-4-6` adds context-aware findings using the playbook, negotiation history, register and team notes. Every quote Claude returns is string-matched against the contract; unverified ones are labelled and downgraded. | Yes |
| **Ask about this contract** | Grounded Q&A over the contract, findings and register. | Yes |

Without a key the app runs in **rules + register mode**: everything above except the two Claude rows.

### Guardrails (from the PRD)
- No finding without a clause reference and quote. Claude quotes are verified against the source text.
- No green "safe to sign" state. Best status: "No blocking issues found. Karandeep's sign-off is still required".
- High findings ask for a logged human decision.
- Escalate to counsel when: value ≥ $150k with open High findings, a conflict with a signed commitment, a HIPAA/GDPR document gap, or a "non-negotiable" template with High findings.

## Results on the 15 incoming drafts (rules + register mode)

| Draft | What it catches |
|---|---|
| Gulf Crown MSA ($140k, due 10 Oct) | **Al Noor GCC non-compete conflict** (runs to 14 Sep 2029, binds affiliates), LD on total contract value with no client-delay carve-out, Saudi law, 60-day payment |
| BlueOrchid pilot | Al Noor conflict: Annexure B lists Dubai and Muscat properties ("just India hotels I think") |
| TravelHub | Wrong entity (AtliQ Inc for a UAE client), invoices from Pvt Ltd, and Al Noor conflict (hotel ranking for UAE/KSA = distribution services to hotels, cl. 1.11) |
| Harrington MSA + BAA ($210k) | Unsigned BAA, **no subcontractor BAA** (C-044 covers CareBridge only), PHI possibly already in Pune (huddle notes), $5M cyber vs $1M held, uncapped per-day LD, one-sided liability, indemnity for client negligence, pre-existing IP assigned |
| Daniel Ortiz contractor | Missing subcontractor BAA for Harrington EHR work |
| Marcus Reed contractor | **India template and Indian law for a US freelancer**, wrong entity, exclusivity + worldwide non-compete, INR at AtliQ's discretion |
| Kriti Data Labs | **120-day pay-when-paid**, uncapped 2%/day LD, one-sided cap, unpaid WIP on termination (all as Fairness) |
| Lakeshore | $72/hr Sr DE breaks Crestline's $85 MFN floor (retroactive credit) |
| Rheinwerk | PipeKit "sole owner" warranty vs Northwind assignment; SOW (Annex 1) and DPA (Annex 3) not attached; German-law liability carve-out correctly rated Low |
| Datavane | Breaches CloudSpan exclusivity in India + GCC; 24-month account restriction; uncapped indemnity vs $10k cap |
| FinServe "mutual" NDA | Only binds AtliQ; hidden 12-month non-compete |
| Sunrise SOW-2, LoopMart NDA, Daniel Ortiz NDA | No blocking issues (the clean controls) |

These are pinned in `tests/test_golden_cases.py` (13 tests); `tests/test_review_findings.py` adds 17 regression tests for the 6 Oct 2026 code review.

## Run it locally

Requires Python 3.10+.

```bash
cd contract-analyzer
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. To turn on the Claude review, either set an environment variable before running:

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."
# macOS/Linux
export ANTHROPIC_API_KEY=sk-ant-...
```

or copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and put the key there (it is git-ignored).

Run the golden tests: `pip install pytest && python -m pytest -q`

## Deploy with GitHub Actions → GitHub Pages (free)

`.github/workflows/deploy.yml` runs on every push to `main`:

1. **test**: installs `requirements.txt`, runs the 30 tests, and renders the app once with Streamlit's `AppTest`.
2. **build**: `site/build_site.py` packages the app and dataset into a static page that runs Streamlit in the browser ([stlite](https://github.com/whitphx/stlite) + Pyodide), then `site/smoke_check.py` opens it in headless Chromium and waits for the Gulf Crown review to show the Al Noor conflict.
3. **deploy**: publishes `_site/` to GitHub Pages at `https://<your-user>.github.io/<repo>/`.

One-time setup: in the repo go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.

The Pages build runs in **rules + register mode** (no Claude review, because a public static page cannot keep an API key secret) and accepts Word/text/Markdown uploads (PDF parsing needs a native library Pyodide cannot load). The first load takes about a minute while Python downloads into the browser. For the full version with Claude, deploy the same repo on Streamlit Community Cloud (below).

## Deploy (free) on Streamlit Community Cloud

Vercel's free tier runs short-lived serverless functions and cannot host a Streamlit server (it needs a long-running process with websockets), so the prototype deploys to **Streamlit Community Cloud**, which is free and built for this.

1. Create a new GitHub repository (public or private) and push this folder to it:
   ```bash
   cd contract-analyzer
   git init
   git add .
   git commit -m "AtliQ Contract Risk Analyzer prototype"
   git branch -M main
   git remote add origin https://github.com/<your-user>/atliq-contract-analyzer.git
   git push -u origin main
   ```
   Check that `data/` (the synthetic dataset) is included and `.streamlit/secrets.toml` is not.
2. Go to https://share.streamlit.io, sign in with GitHub, click **Create app → Deploy a public app from GitHub**.
3. Repository: your repo · Branch: `main` · Main file path: `app.py` · (Advanced settings) Python 3.11.
4. Optional: under **Advanced settings → Secrets**, paste `ANTHROPIC_API_KEY = "sk-ant-..."` to enable the Claude review. Without it the app runs in rules + register mode.
5. Click **Deploy**. You get a public `https://<name>.streamlit.app` URL for the demo video and presentation.

## Project layout

```
contract-analyzer/
├── app.py                    Streamlit UI (review, register, queue, how it works)
├── analyzer.py               Pipeline + Claude review, quote verification, verdict, brief export
├── rules.py                  Document profiling + playbook rules (deterministic)
├── commitments.py            Register conflict checks + TF-IDF retrieval over signed clauses
├── completeness.py           Document-set rules (HIPAA, GDPR, missing annexes)
├── data_loader.py            Dataset loading, clause splitting, PDF/DOCX extraction, tracker matching
├── commitment_register.json  Human-verified register of obligations from signed contracts
├── build_register.py         Re-extracts the register with Claude (claude-haiku-4-5), drops unverifiable quotes
├── tests/test_golden_cases.py
├── tests/test_review_findings.py
├── data/                     The synthetic AtliQ dataset (tracker, 17 signed, 15 incoming, notes)
├── requirements.txt
└── .streamlit/               config.toml, secrets.toml.example
```

## Models and cost

Model choices follow the PRD and cost model (Deliverables 3 and 4): `claude-sonnet-4-6` for the risk review and Q&A, `claude-haiku-4-5` for register extraction. Both are overridable with `ATLIQ_REVIEW_MODEL` / `ATLIQ_EXTRACT_MODEL`. The playbook + register system prompt is marked for prompt caching, so repeated reviews pay full price for it only once per cache window. One review sends roughly the contract (3k-6k tokens) plus ~8k tokens of cached playbook/register context.

## Data notes and limitations

- The dataset is unchanged. The register was compiled by reading every signed contract and is verified clause by clause against the source files; `build_register.py` is the repeatable path for new contracts.
- AtliQ's insurance limits ($1M cyber) come from the 27 Sep Harrington huddle notes; other policy limits are unknown, so higher requirements are flagged as "verify".
- Rules are tuned to this dataset's drafting. Uploaded third-party contracts will rely more on the Claude layer; scanned PDFs need OCR first (pdfplumber reads text-layer PDFs only).
- Tracker matching uses the counterparty name; uploads for unknown counterparties get no tracker context.
