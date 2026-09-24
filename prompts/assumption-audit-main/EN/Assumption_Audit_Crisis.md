# Analytical Prompts – Crisis Version (V1.0.0 – Assumption Audit)

## 12C. Assumption Audit (CRISIS PROTOCOL – 90 seconds)
**Prompt**: Run a fast “Assumption Audit” for [topic] in the context of [scenario].  
**Rules**: Hard rhythm. No filler. Separate facts from hypotheses. Don’t explain—cut.
- Without direct evidence **do not claim intent**. Describe the mechanism. Motive only as Hypothesis + 1 benign alternative.

1) **CLASSIFY**
   - A politics/public sector | B product/UX | C AI/algorithm | D mixed  
   - One-line modules: CSH always + ISO 31000 always; OECD/ISO 9241-210 only B/D; ALTAI/NIST only C/D.

2) **RED FLAG (1 sentence)**
   - “Hidden assumption: [X] is presented as fact even though it is a choice.”
   - **Status**: Fact/Hypothesis/Question + Evidence Tier (A/B/C) + what’s missing to confirm + stop rule (1 short line).

3) **CORES+ (6 lines)**
   - **Authority**: who decided + who is accountable  
   - **Profit**: who benefits from the status quo/default  
   - **Metric**: what is being optimized  
   - **Default**: what is default + cost of opting out  
   - **Costs**: who bears them  
   - **Excluded alternative**: what was ruled out as “unrealistic” / out of scope

4) **3 TRADE-OFFS (3 lines)**
   - “X over Y; cost borne by Z.”

5) **2 ALTERNATIVES (2 lines)**
   - Option 1: 1 sentence cost/risk  
   - Option 2: 1 sentence cost/risk  
   - (If rushed: do a “default switch” — flip the default.)

6) **TIME (sunsetting)**
   - “When does this automatically expire unless benefits are proven?”  
   - Provide deadline + minimum proof (metric + threshold).

7) **PRE-MORTEM (gaming the system)**
   - 1) Tick-box compliance: how does it become paper-only?  
   - 2) Bypass: how is it dodged in practice?  
   - 3) **Malicious compliance**: what extreme by-the-book behavior destroys the goal?

8) **3 INTERVENTIONS (3 lines)**
   - Visible opt-out without penalties.  
   - Justify the metric + publish alternatives.  
   - Sunset/review deadline + independent audit + remedy path.

9) **2 PUBLISH-READY SENTENCES**
   - Sentence 1: “This isn’t necessity; it’s a choice…” (name it)  
   - Sentence 2: “Efficient by which metric—and at whose expense?”

---

## 12C META-PROMPT (V1.0.0 – copy/paste)
Apply the Crisis Assumption Audit to [TOPIC] in the context of [CONTEXT]. Hard rhythm. Separate facts from hypotheses. Output exactly: (1) CLASSIFY A/B/C/D + active modules; (2) RED FLAG (1 sentence “Hidden assumption…”); (3) CORES+ (6 lines); (4) 3 TRADE-OFFS; (5) 2 ALTERNATIVES; (6) TIME (sunset); (7) PRE-MORTEM (tick-box, bypass, malicious compliance); (8) 3 INTERVENTIONS; (9) 2 PUBLISH-READY SENTENCES.
