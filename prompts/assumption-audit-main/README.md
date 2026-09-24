# Assumption Audit – Audit-first Prompt Toolkit (v1.0.3)

Bilingual (CZ/EN) prompt set for **surfacing hidden premises**:
defaults, incentives, accountability gaps, time traps (sunsetting/review), and gaming the system.

This is a **standalone repo** (not a strategy prompt library).

---

## What this is (in one line)

A copy‑paste audit protocol that forces “neutral language” back into **accountability**:
**who decides, who benefits, what metric, what default, who pays, what alternative was excluded, and when it expires**.

---

## What you get from it

Use it when you want to:
- break claims like “it must be done” / “it’s just technical” / “the process decided”,
- identify **Authority vs Profit** (decision power ≠ who benefits),
- expose **defaults** and the **cost of opting out**,
- force a **sunset/review** instead of “permanent by inertia”,
- stress-test for **tick‑box compliance** and **malicious compliance**,
- produce a publishable comment without overclaiming intent.

---

## How to apply (60 seconds)

1) Pick **Crisis** (fast) or **Full** (deep).
2) Copy the prompt from `CZ/` or `EN/`.
3) Replace placeholders `[téma]/[topic]` and `[scénář]/[scenario]`.
4) Paste the article/text/data under the prompt.
5) Enforce the mandatory output format, especially:
   - **STATUS** (Fact/Hypothesis/Question + Evidence Tier A/B/C + missing proof + stop rule),
   - **CORES+** (Authority vs Profit, Metric, Default, Costs, Excluded alternative).

---

## Which file should I use?

### Crisis (90 seconds) – fast commentary
- `CZ/Assumption_Audit_Crisis.md`
- `EN/Assumption_Audit_Crisis.md`

Use when you need: red flag + CORES+ + trade-offs + alternatives + TIME(sunset) + pre‑mortem + 2 publish‑ready sentences.

### Full – deep audit / policy / institutional analysis
- `CZ/Assumption_Audit.md`
- `EN/Assumption_Audit.md`

Use when you need: boundary critique (CSH), risk mapping (ISO 31000 logic), governance checks (ALTAI/NIST), monitoring signals.

---

## Non-paranoia guardrails (built in)

- **No intent claims without evidence**: describe mechanisms; motive only as Hypothesis + 1 benign alternative.
- **STATUS**: Fact / Hypothesis / Question + confidence.
- **Evidence Tier**: A primary / B credible secondary / C signals-only.
- **Falsifier + Missing proof**: what would flip your conclusion and what’s needed to confirm.
- **Stop rule**: define what counts as “enough answer”.

This keeps the audit an **alarm**, not a verdict.

---

## Cheat Sheet
- `docs/CHEAT_SHEET_CZ.md` / `docs/CHEAT_SHEET_EN.md` — one-page quick reference for crisis use.

## Repository structure

- `CZ/` and `EN/` — full + crisis protocols
- `templates/` — copy/paste meta-prompts
- `examples/` — output examples:
  - `example_output_*` — fictional format demo
  - `golden_sample_*` — real-world cases (policy / UX / AI)

---

## Golden samples (real-world)

- UX: CNIL cookie refusal asymmetry (Google/Facebook)  
- Policy: EU Digital COVID Certificate extension + time guardrail  
- AI/Automation: Australia “Robodebt” automated debt raising (averaged income)

---

## License

CC BY 4.0 — share/adapt (including commercially) with attribution.
See `LICENSE.md`.
