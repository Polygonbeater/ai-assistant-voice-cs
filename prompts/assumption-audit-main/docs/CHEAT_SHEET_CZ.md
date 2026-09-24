# Assumption Audit – Cheat Sheet (CZ) (v1.0.3)

Jednostránkový tahák pro rychlé použití.  
Cíl: udržet audit jako **alarm, ne rozsudek**.

---

## Kdy to použít (rychlá volba)

Použij audit, když slyšíš:
- „musí se“, „nelze jinak“, „je to jen technické“, „best practice“, „takový je proces“, „data ukazují“.

---

## Krizová kostra (90 sekund)

1) **KLASIFIKACE**: A politika | B produkt/UX | C AI/algoritmus | D smíšené  
2) **ČERVENÁ** (1 věta)  
3) **STATUS** (1 řádek)  
4) **JÁDRA+** (6 řádků)  
5) **3 trade-offy**  
6) **2 alternativy**  
7) **ČAS (sunset)**  
8) **PRE-MORTEM** (tick-box / obcházení / malicious compliance)  
9) **3 intervence**  
10) **2 věty k publikaci**

---

## ČERVENÁ (šablony)

- „Skrytý předpoklad: **[X]** se prezentuje jako fakt, ačkoliv jde o volbu.“  
- „Volba maskovaná jako nutnost: **[X]** (protože se schovává **metrika/default/odpovědnost**).“  
- „Proces nahrazuje důvod: **[X]** – ale chybí srovnání alternativ a nákladů.“

---

## STATUS (anti-paranoia pojistka)

**Formát (1 řádek):**  
`STATUS: [Fakt/Hypotéza/Otázka], důvěra [nízká/střední/vysoká], Evidence Tier [A/B/C], chybí [min. důkaz], stop rule: [co je „dost“].`

**Evidence Tier**
- **A** = primární zdroj (zákon, rozhodnutí, oficiální report, data)
- **B** = důvěryhodné sekundární (seriózní média, akademické shrnutí)
- **C** = indicie / nepřímé signály (domněnky bez tvrdého podkladu)

**Zákaz úmyslu bez důkazu**  
Motiv nikdy netvrď jako fakt. Motiv = jen Hypotéza + 1 benigní alternativa.

---

## JÁDRA+ (6 řádků)

1) **Autorita**: kdo rozhodl + kdo ručí  
2) **Profit**: kdo těží ze status quo/defaultu  
3) **Metrika**: co se optimalizuje  
4) **Default**: co je výchozí + cena opt-outu  
5) **Náklady**: kdo je nese  
6) **Vyřazená alternativa**: co bylo vytlačeno mimo zadání

---

## Trade-off šablona (3 řádky)

- „**X před Y**, dopad nese **Z**.“

Příklady X/Y:
- rychlost vs. přesnost
- plynulost vs. legitimita
- výnos vs. autonomie
- kontrola vs. soukromí
- standardizace vs. pluralita

---

## Alternativy (2 řádky)

- Varianta 1: **[co]** (cena/riziko: **[1 věta]**)  
- Varianta 2: **[co]** (cena/riziko: **[1 věta]**)  
Tip: když nestíháš, udělej **default switch** („co kdyby výchozí stav byl opačný?“).

---

## ČAS (sunset) – povinná otázka

- „Kdy to **automaticky zanikne**, pokud se neprokáže přínos?“  
- „Jaký je **minimální důkaz přínosu** (metrika + práh + termín)?“

---

## PRE-MORTEM (3 bullet points)

1) Tick-box: jak to splní jen na oko?  
2) Obcházení: jak se to obejde v praxi?  
3) Malicious compliance: jak extrémní dodržení zničí cíl?

---

## 3 intervence (hotové formulace)

- „Opt-out viditelně a bez penalizace.“  
- „Povinné zdůvodnění metriky + zveřejnění alternativ.“  
- „Sunset termín + nezávislý audit + opravný prostředek.“

---

## 2 věty k publikaci (punchline šablony)

- „Tohle není nutnost, tohle je volba – a chybí srovnání alternativ.“  
- „Efektivní podle jaké metriky a na účet koho?“  
- „Kdo rozhoduje a kdo profituje? To není totéž.“

---

## Mini checklist (když máš 10 sekund)

- Skrytý předpoklad?  
- Kdo profituje?  
- Jaká metrika?  
- Jaký default a cena opt-outu?  
- Kdy to končí?
