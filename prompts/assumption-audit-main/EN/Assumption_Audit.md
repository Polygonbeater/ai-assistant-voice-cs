# Analytical Prompts (Version 1.0.0 – Assumption Audit)

## Introduction
This prompt extends the V3.1 set with a method for **surfacing assumptions**: hidden premises, defaults, incentives, and procedures that masquerade as “neutral necessity”.
It works across politics, institutions, organizations, and digital products.

---

## 12. Assumption Audit (CSH + ISO 31000 + OECD + ISO 9241-210 + ALTAI + NIST AI RMF)
**Prompt**: Perform an “Assumption Audit” for [topic] in the context of [scenario]. Goal: expose where choice is disguised as fact, where defaults steer outcomes, and where “process” replaces justification.  
**Rules**: (a) Separate facts from hypotheses. (b) Anchor claims in data or state what would falsify them. (c) Write with a hard rhythm—no filler.  

**Guardrails (alarm, not verdict)**:
- ****No intent claims without evidence****: if you lack direct support, describe the mechanism, not motives.
- **Three conclusion states**: label each key claim as **Fact**, **Hypothesis**, or **Question**.
- **Steelman + Abuse**: always include 1 most benign explanation and 1 highest-risk explanation (and why).
- **Falsifier**: state what must be true for the opposite conclusion to hold.
- **Missing evidence**: specify the minimal proof needed to upgrade a hypothesis.

**Additional guardrails (anti-paranoia)**:
- **Evidence Tier**: label support strength (A primary source / B credible secondary / C signals only).
- **Green check**: give 1 reason the action could be legitimate without bad intent.
- **Stop rule**: define what counts as “enough answer” and when the audit ends (avoid infinite skepticism).


**Workflow note**: If the user prompt is a closed question or a pre-made conclusion, rewrite it as a **systems problem** first.

1. **Validate inputs**
   - Verify facts and timeline (primary sources, documents, data).
   - Fill missing context: actors, mandates, incentives, data.
   - List uncertainties and what would confirm/deny them.

2. **Reframe the problem (debias the prompt)**
   - Rewrite as: “What systems problem are we solving, and what are its boundaries?”
   - Add 1 sentence: what the prompt assumes as “given”.

3. **Classify the case (module activation)**
   - A politics/public sector  B product/UX  C AI/algorithm  D mixed.
   - Activate: **CSH always**, **ISO 31000 always**; **OECD + ISO 9241-210** if B/D; **ALTAI** if C/D or public automation; **NIST AI RMF** if C/D.

4. **Extract assumption statements (triggers)**
   - Pull phrases like: “must”, “cannot be otherwise”, “just technical”, “best practice”, “the process is”, “the data shows”.
   - For each: what it closes (alternatives / accountability / metric / impact / time horizon).

5. **CSH: Set system boundaries (boundary critique)**
   - Who defined the problem and success?
   - What’s inside scope, what got pushed out?
   - Who has voice, who is excluded, who bears consequences?

6. **Authority and accountability**
   - Who decided? Who executes? Who has veto power? Who is liable?
   - What remedies exist: appeal, review, audit, court, independent oversight?

7. **Incentive Audit (Authority vs. Profit)**
   - Separate: **who decides** vs **who benefits**.
   - Who profits from preserving the status quo (the default)?
   - What are the incentives of key actors (money, reputation, power, convenience, risk avoidance)?

8. **Goal, metric, incentives (KPIs vs. KBIs)**
   - Stated goal vs actual goal implied by incentives and system behavior.
   - Define 2–3 **KPIs** (outcomes) and 2–3 **KBIs** (behaviors) the system reinforces.
   - Who owns the metrics, and who can change them?

9. **Defaults and cost of opting out**
   - What is the default?
   - What does opting out cost (time/money/stigma/loss of service)?
   - Is opt-out symmetric with opt-in, or penalized?

10. **OECD: Dark patterns / steering (if B/D)**
   - Identify one-direction steering (nudge → sludge → dark pattern).
   - Check: hidden options, misleading copy, infinite flows, aggressive notifications, asymmetrical buttons.
   - For each: how it changes decisions and who benefits.

11. **ISO 9241-210: Human-centred impacts (if B/D)**
   - Who is the user and who is a vulnerable group?
   - What negative impacts appear (errors, stress, addictive loops, exclusion)?
   - What usability and wellbeing testing would look like (KBIs)?

12. **ALTAI: Transparency and governance (if C/D or public automation)**
   - Is “why” and “how” clear (documentation, explainability, communication)?
   - Who is responsible, and how fast is redress?
   - How do oversight, audit, and revision work?

13. **NIST AI RMF: AI risk (if C/D)**
   - **Govern**: ownership of risk and policies.
   - **Map**: use context + failure modes + affected groups.
   - **Measure**: reliability, bias, robustness, safety metrics.
   - **Manage**: mitigations, monitoring, incident response.

14. **ISO 31000: Risk map (always)**
   - Identify 6–10 risks (rights, safety, finance, reputation, systemic effects).
   - For each: probability %, impact 1–10, who bears the cost.
   - Propose treatment + residual risk.

15. **Alternatives + default switch**
   - Propose at least 2 realistic alternatives.
   - Flip the default: “what if the default were the opposite?”
   - For each: benefits, risks, who gains, who pays.

16. **Temporal Audit (time dimension)**
   - What is treated as permanent even though it shouldn’t be?
   - Set **sunset/review**: when does it automatically expire unless benefits are proven?
   - Define minimum proof (metric + threshold + deadline).

17. **Pre-mortem + tick-box test + malicious compliance**
   - Where does compliance become paper-only?
   - How is it bypassed in practice?
   - **Malicious compliance**: what extreme “by-the-book” behavior would destroy the original goal?
   - What safeguards prevent this (audit, effect measurement, sanctions, review)?

18. **Bias check + disconfirming test**
   - Check at least: authority bias, availability, narrative bias, illusion of control.
   - Add 1 falsifier: “What must be true for the opposite conclusion to hold?”

19. **Interventions: meaningful friction + monitoring**
   - Propose 3 interventions that restore real choice (not destruction):
     1) visible opt-out without penalties,
     2) mandatory metric justification + publication of alternatives,
     3) sunset/review deadline + independent audit + remedy path.
   - Define 3 signals of “assumption re-closure” (e.g., opt-out cost rises, reviews disappear, “no longer up for discussion”).
   - Set review cadence (monthly/quarterly).

---

## Mandatory output format
- A) **RED FLAG**: “Hidden assumption: [X] is presented as fact even though it is a choice.”
- A.1) **STATUS**: Fact/Hypothesis/Question + confidence (low/medium/high) + **Evidence Tier (A/B/C)** + what’s missing to confirm + stop rule (what counts as enough).
- B) **CORES+** (6 lines):  
  1) Authority (who decided & who is accountable)  
  2) Profit (who benefits from the status quo/default)  
  3) Metric (what is optimized)  
  4) Default (what is default + cost of opting out)  
  5) Costs (who bears them)  
  6) Excluded alternative (what was ruled out)
- C) **3 trade-offs**: “X over Y; cost borne by Z.”
- D) **2 alternatives** + cost/risk
- E) **3 interventions** + **review condition** (when to change or roll back)

**Context**: How does this relate to [scenario]?  
**Recommendation**: For political commentary, institutional audits, and both digital and non-digital systems.

---

## 13. BONUS: Meta-prompt (V1.0.0 – commentary-ready)
**Prompt**: Apply the “Assumption Audit” to [topic] in the context of [scenario]. Classify A/B/C/D and activate modules accordingly. Hard rhythm. Separate facts from hypotheses. First reframe the prompt as a systems problem. Output exactly:
1) CLASSIFICATION + active modules  
2) RED FLAG (format “Hidden assumption…”)  
3) CORES+: Authority vs Profit / Metric / Default / Costs / Excluded alternative  
4) TIME: sunset condition + review deadline  
5) PRE-MORTEM: 2 bypass routes + 1 malicious compliance scenario  
6) PUBLISH: 2 sentences that break the “only rational solution” narrative
