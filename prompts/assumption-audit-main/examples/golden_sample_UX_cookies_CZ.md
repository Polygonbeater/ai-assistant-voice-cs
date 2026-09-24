# Golden sample (CZ) – UX audit: „Odmítnout cookies musí být stejně snadné jako přijmout“

**Případ (reálný)**: Francouzský regulátor CNIL uvedl, že weby facebook.com, google.fr a youtube.com neumožňovaly odmítnout cookies stejně jednoduše jako je přijmout, a uložil pokuty (Google 150 mil. €, Facebook 60 mil. €) a příkaz k nápravě.  
**Zdrojový rámec**: OECD (steering/dark patterns) + ISO 9241-210 (uživatelský dopad) + odpovědnost (compliance).

---

## Krizový Audit samozřejmostí (B – produkt/UX)

1) **KLASIFIKACE**: B (produkt/UX). Moduly: CSH + ISO 31000 + OECD + ISO 9241-210.  
2) **ČERVENÁ**: Skrytý předpoklad: „Souhlas s cookies“ se prezentuje jako neutrální klik, ačkoliv je to volba, kterou UI může asymetricky tlačit.  
   **STATUS**: Fakt (o zjištění CNIL), důvěra vysoká, Evidence Tier A. Chybí: detailní UX flow pro konkrétní verzi stránky; stop rule: doložené 1‑klik „Reject all“ + auditní log změny.

3) **JÁDRA+**
- **Autorita**: CNIL (dohled + sankce) / provozovatelé webů (implementace UI).  
- **Profit**: reklama a tracking (Hypotéza: větší souhlas → více dat/monetizace; Evidence Tier B/C).  
- **Metrika**: míra consentu, retence, výnos z personalizace.  
- **Default**: „přijmout“ je snadné; „odmítnout“ je dražší (více kroků).  
- **Náklady**: uživatel (ztráta kontroly, čas, soukromí); firma (compliance náklady).  
- **Vyřazená alternativa**: symetrická volba (Accept/Reject stejně viditelné a stejně rychlé).

4) **3 TRADE-OFFY**
- Výnosy z personalizace před autonomií uživatele; dopad nese uživatel.  
- UX plynulost pro consent před legitimitu souhlasu; dopad nese právo (riziko neplatného souhlasu).  
- Krátkodobá optimalizace před dlouhodobou důvěru; dopad nese značka.

5) **2 ALTERNATIVY**
- Varianta 1: „Accept all“ a „Reject all“ vedle sebe (1 klik / 1 klik). Riziko: nižší consent rate.  
- Varianta 2: granularita až po volbě (nejdřív Accept/Reject, pak „nastavit“). Riziko: více práce na implementaci.

6) **ČAS (sunset)**
- A/B test steeringu musí mít deadline: do 30 dnů buď prokázat, že je volba symetrická, nebo experiment ukončit.

7) **PRE-MORTEM**
- Tick-box: přidá se „Reject“, ale schová se do sekundárního menu.  
- Obcházení: „cookie wall“ (služba jen po souhlasu) tam, kde to není nutné.  
- Malicious compliance: tlačítko „Reject“ existuje, ale po odmítnutí se stránka rozbije / zhorší funkce.

8) **3 INTERVENCE**
- Povinná symetrie: „Reject all“ stejně viditelné a stejně rychlé jako „Accept all“.  
- Povinné odůvodnění metriky: proč se sleduje a co je minimální rozsah.  
- Nezávislý UX audit + veřejný changelog consent flow.

9) **2 VĚTY K PUBLIKACI**
- „Tohle není technický detail: UI rozhoduje, jestli je souhlas volba, nebo past.“  
- „Efektivní podle jaké metriky – a na účet koho, když odmítnout stojí víc než přijmout?“

---

## Zdroje
- CNIL (leden 2022): oznámení sankcí a zjištění „odmítnout není stejně snadné jako přijmout“.  
- Reuters (6. 1. 2022): shrnutí pokut a požadavku na nápravu.
