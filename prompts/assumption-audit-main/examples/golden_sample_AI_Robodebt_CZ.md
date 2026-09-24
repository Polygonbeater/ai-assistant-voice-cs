# Golden sample (CZ) – Algoritmický audit: Australský „Robodebt“ (automatizované vymáhání dluhů)

**Případ (reálný)**: „Robodebts“ byly dluhy vytvářené mezi červencem 2015 a listopadem 2019 v rámci Income Compliance Programu. Byly zvedané pomocí porovnání dávek s **průměrovanými** (averaged) údaji o příjmech z ATO. Následné prověřování a závěry Royal Commission popisují schéma jako nezákonné/nesprávné a s těžkými dopady.  
**Zdrojový rámec**: CSH (hranice a legitimita) + ISO 31000 (rizika) + ALTAI/NIST (governance, odpovědnost, řízení rizik).

---

## Krizový Audit samozřejmostí (C – AI/algoritmus / automatizace)

1) **KLASIFIKACE**: C (automatizované rozhodování/algoritmus). Moduly: CSH + ISO 31000 + ALTAI + NIST AI RMF.  
2) **ČERVENÁ**: Skrytý předpoklad: „průměrovaná data stačí jako důkaz dluhu“ se prezentuje jako fakt, ačkoliv jde o volbu metodiky, která mění břemeno dokazování a míru chyb.  
   **STATUS**: Smíšené — Fakt (časové vymezení a použití averaged ATO income), důvěra vysoká, Evidence Tier A. Hodnotící závěry o škodách: Evidence Tier A/B (oficiální report + veřejná sdělení). Chybí: veřejně srovnatelné metriky false‑positive/false‑negative v čase; stop rule: zveřejnění míry chyb + nezávislý audit + jasná náprava pro chybně zasažené.

3) **JÁDRA+**
- **Autorita**: Services Australia / vláda (nastavení režimu) + legislativní rámec (co je „důkaz“).  
- **Profit**: fiskální úspory / „výkon“ compliance (Hypotéza: tlak na výnosy a rychlost; Evidence Tier B/C).  
- **Metrika**: objem zjištěných dluhů, rychlost vymáhání, „detekce nesouladu“.  
- **Default**: systém generuje dluh jako výchozí; občan musí vyvracet (asymetrie).  
- **Náklady**: občané (čas, stres, finanční nejistota), stát (nápravy, reputace, právní riziko).  
- **Vyřazená alternativa**: ověřování na základě primárních dokladů (payslips) před vystavením dluhu; nebo lidský review u hraničních případů.

4) **3 TRADE-OFFY**
- Rychlost a škálování před přesnost, dopad nesou zranitelní.  
- „Výkonnost“ compliance před právní jistotu, dopad nese legitimita státu.  
- Automatizace před opravdovou odpovědnost, dopad nese náprava a důvěra.

5) **2 ALTERNATIVY**
- Varianta 1: dluh se vystaví až po získání primárního důkazu (nižší rychlost, vyšší přesnost).  
- Varianta 2: automat jen jako „triage“ + povinný lidský review u všech zásadních dopadů (vyšší náklady, vyšší spravedlnost).

6) **ČAS (sunsetting)**
- Každý automatizovaný režim vymáhání musí mít tvrdý sunset (např. 12 měsíců) a pokračuje jen při prokázání: (a) nízké chybovosti, (b) dostupné nápravy, (c) transparentní metriky.

7) **PRE-MORTEM**
- Tick-box: existuje „review“, ale je přetížený a jen razítkuje výstupy.  
- Obcházení: systém posílá rozhodnutí „k potvrzení“, ale lidský review nemá informace.  
- Malicious compliance: úřad vyžaduje dokumenty, které lidé reálně nemohou dodat, a tím formalizuje nemožnost obrany.

8) **3 INTERVENCE**
- Povinné zveřejnění metrik: chybovost, odvolání, doba nápravy, dopady na skupiny.  
- Právo na člověka + rychlá náprava (refund, omluva, stop vymáhání při sporu).  
- Nezávislý audit + jasná odpovědnost „kdo ručí“ za model/metodu a její změny.

9) **2 VĚTY K PUBLIKACI**
- „Když algoritmus dělá dluh výchozím stavem, stát musí dokazovat, ne občan.“  
- „Efektivní podle jaké metriky – a na účet koho, když cena omylu padá na nejslabší?“

---

## Zdroje
- Services Australia: definice „robodebts“, období a použití averaged ATO income (Income Compliance Program).  
- Royal Commission: publikované závěry a report k Robodebt schématu (oficiální zdroj).
