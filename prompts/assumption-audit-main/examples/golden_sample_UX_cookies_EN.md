# Golden sample (EN) – UX audit: “Rejecting cookies should be as easy as accepting”

**Case (real)**: France’s data protection authority (CNIL) stated that facebook.com, google.fr and youtube.com did not allow users to refuse cookies as easily as they could accept them, and imposed fines (Google €150m, Facebook €60m) plus an order to comply.  
**Frame**: OECD (steering/dark patterns) + ISO 9241-210 (human impact) + accountability (compliance).

---

## Crisis Assumption Audit (B – product/UX)

1) **CLASSIFY**: B (product/UX). Modules: CSH + ISO 31000 + OECD + ISO 9241-210.  
2) **RED FLAG**: Hidden assumption: “cookie consent” is presented as a neutral click even though UI can asymmetrically steer that choice.  
   **STATUS**: Fact (CNIL finding), high confidence, Evidence Tier A. Missing: exact UI flow snapshots for the specific version; stop rule: documented 1‑click “Reject all” + audited change log.

3) **CORES+**
- **Authority**: CNIL (oversight/sanctions) / site operators (UI implementation).  
- **Profit**: advertising & tracking (Hypothesis: higher consent → more data/monetization; Evidence Tier B/C).  
- **Metric**: consent rate, retention, personalization revenue.  
- **Default**: “accept” is easy; “reject” is costlier (more steps).  
- **Costs**: user (loss of control, time, privacy); company (compliance costs).  
- **Excluded alternative**: symmetric choice (Accept/Reject equally visible and equally fast).

4) **3 TRADE-OFFS**
- Personalization revenue over user autonomy; cost borne by users.  
- Frictionless consent UX over consent validity; cost borne by legal legitimacy.  
- Short-term optimization over long-term trust; cost borne by the brand.

5) **2 ALTERNATIVES**
- Option 1: “Accept all” and “Reject all” side-by-side (1 click / 1 click). Risk: lower consent rate.  
- Option 2: granularity after the first choice (Accept/Reject first, then “settings”). Risk: implementation work.

6) **TIME (sunset)**
- Any steering A/B test must have a deadline: within 30 days prove symmetry, or terminate the experiment.

7) **PRE-MORTEM**
- Tick-box: add “Reject” but hide it in secondary menus.  
- Bypass: cookie walls where not necessary.  
- Malicious compliance: “Reject” exists, but rejecting breaks functionality / degrades experience.

8) **3 INTERVENTIONS**
- Enforce symmetry: “Reject all” as visible and as fast as “Accept all”.  
- Mandatory metric justification: why it’s measured and minimum scope.  
- Independent UX audit + public changelog of consent flows.

9) **2 PUBLISH-READY SENTENCES**
- “This isn’t a technical detail: UI decides whether consent is a choice or a trap.”  
- “Efficient by which metric—and at whose expense if rejecting costs more than accepting?”

---

## Sources
- CNIL (Jan 2022 newsletter): sanctions announcement and “refusing not as easy as accepting”.  
- Reuters (Jan 6, 2022): fines and compliance order summary.
