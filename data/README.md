# AtliQ Contract Review Dataset — Data Dictionary

**Everything here is fully synthetic.** It is inspired by AtliQ's real situation, but it contains no real client names, contracts or legal advice. Several clients also appear in the Capstone 1 dataset (Acme, Northwind, Sunrise Foods, PayTrack, Trustline, BlueOrchid, TravelHub, Meridian Healthcare, FinServe Capital, GlobalMart, LoopMart), because it's the same company. Treat **"today" as 2026-09-28**.

**Legal caution:** the contracts are written to look realistic, but they are teaching material, not templates. Don't reuse the clauses, and don't read anything here as legal advice about any real jurisdiction.

## The AtliQ people in this data
All AtliQ team members appear by first name with an `@atliq.com` email:
- **Karandeep** (CEO): reviews and signs every contract. AtliQ has no legal team and no head of contracts.
- **Bhavin** and **Dhaval** (founders) and **Jay** (sales executive): bring contracts in and wait on them.
- **Pranav** (CTO): confirms scope, staffing and what can be reused.

Outside counsel is used occasionally: Mehta Rao & Associates (India) and Calloway Stern LLP (US).

## AtliQ sits on different sides of the table
The contracts here aren't all client contracts. AtliQ signs as:
- the **supplier**: client MSAs, SOWs and service agreements, usually on the client's paper;
- the **buyer**: agreements with the agencies and individual freelance contractors AtliQ brings in, on AtliQ's own templates;
- a **partner**: strategic partnership, referral and implementation agreements with platform companies;
- either party to an **NDA**: one-way and mutual, which make up most of the volume.

Some deals are a **bundle** rather than one document. US healthcare work that touches patient data needs an NDA, a HIPAA **Business Associate Agreement (BAA)** and the services contract, and anyone AtliQ brings in to do that work needs matching terms of their own. European work with personal data has its own equivalent (a GDPR data processing agreement).

AtliQ's stated preference is for mutual, balanced terms (a mutual NDA over a one-sided one, a deal that works for both sides), including when a one-sided clause would favour AtliQ. How well its actual contracts live up to that is for you to find.

## How the files connect
- The join keys are the **counterparty name**, the **AtliQ entity**, and the `contract_id` in the tracker.
- A contract under review can't be judged on its own. What AtliQ has *already signed*, and how it has *negotiated before*, sit in other files: some in `signed_contracts/`, some in Jay's half-finished `negotiation_notes.md`, some only in people's memory (the meeting notes).
- There is **no register** of the obligations AtliQ has taken on (non-competes, exclusivity, pricing promises, IP handed over). Nobody at AtliQ has one; that absence is part of the problem.

## What you have

### 1. `contract_tracker.csv`: the contract log as it exists today (48 rows)
A spreadsheet Jay started in 2025 and everyone updates occasionally. Expect blanks, a duplicate, stale statuses and missing file locations.

| Column | Meaning |
|---|---|
| contract_id | Tracker ID |
| counterparty / doc_type | Client and document type (MSA, SOW, NDA, DPA, waiver, etc.) |
| atliq_entity | Which AtliQ entity signs (often blank) |
| client_country | Client's country |
| requested_by | Who brought the contract to Karandeep |
| received_date / signed_date / expiry_date | Dates as recorded, when recorded |
| status | Signed / In review / Awaiting client / Draft / Rejected / Not started (sometimes blank) |
| value_usd | Approximate value |
| file_location | Where the file lives, if anyone wrote it down |
| restrictive_clauses | Meant to record non-competes, exclusivity and the like. Rarely filled in, and not always right |
| notes | Free text |

### 2. `signed_contracts/`: 17 executed documents
Text extracted from signed PDFs, including one scanned file with OCR errors. Client MSAs and SOWs, a waiver letter, NDAs, a strategic partnership agreement, a freelance contractor agreement, and HIPAA Business Associate Agreements, with a mix of clean and one-sided terms. Each file says where it was found; they were scattered across drives, inboxes and laptops before being collected here.

### 3. `incoming/`: 15 drafts waiting for Karandeep's review
Client agreements, NDAs, a Business Associate Agreement, a partnership agreement, and AtliQ's own drafts for an agency and two freelancers. Most are on the other party's paper. Some carry real risk, some only look risky, and at least one is clean. Deadlines and the sellers' context sit in the tracker's `notes` column, not in the contracts.

### 4. `negotiation_notes.md`: how AtliQ has negotiated before
Jay's partial reconstruction, made by searching old inboxes after the 22 Sep meeting, of what AtliQ asked for, conceded or walked away from in past negotiations (2024–2026). Incomplete and unreviewed, and it records what happened, not whether it was right.

### 5. `meeting_notes/`: 4 notes
Read the internal contract-queue meeting (2026-09-22) first; it describes the problem in AtliQ's own words. Italicised lines in parentheses are editorial notes about what happened (or didn't) afterwards. Treat them as ground truth.

### 6. `atliq_entities.md` and `karandeep_contract_checklist.md`
- `atliq_entities.md`: finance's fact sheet on AtliQ's two legal entities and which regions each one serves.
- `karandeep_contract_checklist.md`: the only written record of how contracts get reviewed, with Karandeep's own note on why it isn't working.

## Suggestions
- Pick one incoming contract and try to answer: *"Is it safe for AtliQ to sign this?"* using only these files. Notice how many files you had to open, and how many things you'd never have thought to check.
- Then try: *"What has AtliQ already promised not to do?"* There's no list, so feel the problem before designing anything.
- You may extend this dataset (more contracts, more negotiation history, edge cases you believe should exist) if your solution needs it. Say what you added in your README.
