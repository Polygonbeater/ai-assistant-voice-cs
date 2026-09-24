# Analytické prompty (Verze 1.0.0 – Audit samozřejmostí)

## Úvod
Tento prompt rozšiřuje sadu V3.1 o metodiku pro **odhalování samozřejmostí**: skrytých předpokladů, defaultů, incentivy a procedur, které se tváří jako „neutrální nutnost“.
Je použitelný pro politiku, instituce, organizace i digitální produkty.

---

## 12. Audit samozřejmostí (CSH + ISO 31000 + OECD + ISO 9241-210 + ALTAI + NIST AI RMF)
**Prompt**: Proveď „Audit samozřejmostí“ pro [téma] v kontextu [scénáře]. Cíl: odhalit, kde se volba maskuje jako fakt, kde fungují defaulty a kde „proces“ nahrazuje zdůvodnění.  
**Pravidla**: (a) Odděluj fakta a hypotézy. (b) Každé tvrzení ukotvi daty nebo uveď, co by ho vyvrátilo. (c) Piš tvrdým rytmem, bez omáčky.  

**Pojistky (alarm, ne rozsudek)**:
- ****Bez tvrzení o úmyslu bez důkazu****: pokud nemáš přímý podklad, popisuj mechanismus, ne motiv.
- **Tři stavy závěru**: označ, zda jde o **Fakt**, **Hypotézu**, nebo **Otázku**.
- **Steelman + Abuse**: vždy uveď 1 nejnevinnější vysvětlení a 1 nejrizikovější vysvětlení (a proč).
- **Falsifikátor**: napiš, co by muselo platit, aby byl závěr opačný.
- **Co chybí k potvrzení**: specifikuj minimální důkaz, který by z Hypotézy udělal Fakt.

**Další pojistky (proti paranoidnímu skluzu)**:
- **Evidence Tier**: označ sílu podkladu (A primární zdroj / B důvěryhodné sekundární / C jen indicie).
- **Zelená kontrola**: uveď 1 důvod, proč může být postup legitimní i bez zlého úmyslu.
- **Stop rule**: napiš, co by byla „dostatečná odpověď“ a kdy audit končí (aby se z toho nestal nekonečný skepticism).


**Poznámka (workflow)**: Pokud je zadání formulováno jako uzavřená otázka nebo jako hotový závěr, nejdřív ho přepiš na **systémový problém**.

1. **Validuj vstupy**
   - Ověř fakta a časovou osu (primární zdroje, dokumenty, data).
   - Doplň chybějící kontext: aktéři, pravomoci, incentivy, data.
   - Označ nejistoty a „co chybí k potvrzení“.

2. **Reformuluj problém (proti biasu zadání)**
   - Přepiš téma do podoby: „Jaký systémový problém zde řešíme a jaké jsou jeho hranice?“
   - Uveď 1 větu: co se v zadání předpokládá jako samozřejmé.

3. **Klasifikuj případ (aktivace modulů)**
   - A) Politika/veřejná správa  B) Digitální produkt/UX  C) AI/algoritmus  D) Smíšené.
   - Aktivuj: **CSH vždy**, **ISO 31000 vždy**; **OECD + ISO 9241-210** pokud B/D; **ALTAI** pokud C/D nebo veřejná služba s automatizací; **NIST AI RMF** pokud C/D.

4. **Detekuj věty samozřejmosti (spouštěče)**
   - Vytáhni formulace typu: „musí se“, „nelze jinak“, „je to jen“, „nejracionálnější“, „takový je proces“, „data ukazují“.
   - U každé napiš: *co tím mizí* (alternativa / odpovědnost / metrika / dopad / časový horizont).

5. **CSH: Nastav hranice systému (boundary critique)**
   - Kdo definoval „problém“ a „úspěch“?
   - Co je uvnitř zadání a co bylo vytlačeno ven?
   - Kdo má hlas, kdo je vynechán, kdo nese důsledky?

6. **Autorita a odpovědnost**
   - Kdo rozhodl? Kdo vykonává? Kdo má veto? Kdo ručí?
   - Jak vypadá náprava: odvolání, přezkum, audit, soud, nezávislý dohled?

7. **Incentive Audit (Autorita vs. Profit)**
   - Odděl: **kdo rozhoduje** vs. **kdo profituje**.
   - Kdo těží z udržování status quo (defaultu)?
   - Jaké jsou incentivy všech klíčových aktérů (zisk, reputace, moc, pohodlí, vyhnutí se riziku)?

8. **Cíl, metrika a incentivy (KPIs vs. KBIs)**
   - Deklarovaný cíl vs. skutečný cíl podle incentivy a chování systému.
   - Definuj 2–3 **KPIs** (výsledky) a 2–3 **KBIs** (chování), které systém reálně pěstuje.
   - Kdo metriky vlastní a kdo je může změnit?

9. **Defaulty a cena opt-outu**
   - Co je výchozí nastavení (default)?
   - Kolik stojí volba jinak (čas/peníze/stigma/ztráta služby)?
   - Je opt-out symetrický (stejně snadný jako opt-in), nebo penalizovaný?

10. **OECD: Dark patterns / steering (pokud B/D)**
   - Najdi „tlačení“ jedním směrem (nudge → sludge → dark pattern).
   - Zkontroluj: skryté volby, matoucí texty, nekonečné toky, agresivní notifikace, asymetrie tlačítek.
   - U každého uveď: jak mění rozhodování a komu prospívá.

11. **ISO 9241-210: Human-centred dopady (pokud B/D)**
   - Kdo je uživatel a kdo zranitelná skupina?
   - Jaké jsou negativní dopady použití (chyby, stres, závislostní smyčky, vyloučení)?
   - Jak by vypadalo testování použitelnosti a wellbeing (KBIs)?

12. **ALTAI: Transparentnost a governance (pokud C/D nebo automatizace ve veřejné službě)**
   - Je jasné „proč“ a „jak“ (vysvětlitelnost, dokumentace, komunikace)?
   - Kdo nese odpovědnost a jak rychlá je náprava?
   - Jak funguje dohled, audit, revize modelů/procesů?

13. **NIST AI RMF: Rizika AI (pokud C/D)**
   - **Govern**: kdo vlastní riziko a pravidla?
   - **Map**: scénáře použití + scénáře selhání + dotčené skupiny.
   - **Measure**: metriky spolehlivosti, bias, robustnosti, bezpečí.
   - **Manage**: mitigace, monitoring, incident response.

14. **ISO 31000: Riziková mapa (vždy)**
   - Identifikuj 6–10 rizik (práva, bezpečí, finance, reputace, systémové dopady).
   - U každého uveď: pravděpodobnost %, dopad 1–10, kdo nese náklady.
   - Navrhni ošetření + zbytkové riziko (residual).

15. **Alternativy + default switch**
   - Navrhni minimálně 2 realistické alternativy.
   - Otoč default: „co kdyby výchozí stav byl opačný?“
   - U každé varianty napiš: výhody, rizika, komu pomáhá, koho zatíží.

16. **Temporal Audit (časový rozměr)**
   - Co se tu bere jako trvalé, i když by nemělo?
   - Nastav **sunset/review**: kdy se to musí automaticky přehodnotit, pokud se neprokáže přínos?
   - Jaký je minimální důkaz přínosu (metrika + prahová hodnota + termín)?

17. **Pre-mortem + test tick-boxu + malicious compliance**
   - Kde hrozí splnění „na oko“ (existuje to, ale nefunguje)?
   - Jak se to obejde v praxi?
   - **Malicious compliance**: Jak by vypadalo extrémní dodržení pravidel, které zničí původní cíl?
   - Jaké pojistky tomu brání (audit, měření efektu, sankce, revize)?

18. **Kontrola zkreslení + vyvracející test**
   - Zkontroluj minimálně: autorita, dostupnost, narativ, iluze kontroly.
   - Uveď 1 disconfirming test: „Co by muselo platit, aby byl závěr opačný?“

19. **Intervence: smysluplné tření + monitoring**
   - Navrhni 3 zásahy, které vrací volbu do reality (ne destrukci):
     1) viditelný opt-out bez penalizace,
     2) povinné zdůvodnění metriky + zveřejnění alternativ,
     3) revizní termín (sunset) + nezávislý audit + opravný prostředek.
   - Nastav 3 signály návratu samozřejmosti (např. růst ceny opt-outu, mizí revize, „už se to neřeší“).
   - Urči periodicitu přezkumu (měsíčně/kvartálně).

---

## Povinný formát výstupu
- A) **ČERVENÁ**: „Skrytý předpoklad: [X] se prezentuje jako fakt, ačkoliv jde o volbu.“
- A.1) **STATUS**: Fakt/Hypotéza/Otázka + důvěra (nízká/střední/vysoká) + **Evidence Tier (A/B/C)** + co chybí k potvrzení + stop rule (kdy je „dost“).
- B) **JÁDRA+** (6 řádků):  
  1) Autorita (kdo rozhodl a ručí)  
  2) Profit (kdo těží ze status quo/defaultu)  
  3) Metrika (co se optimalizuje)  
  4) Default (co je výchozí + cena opt-outu)  
  5) Náklady (kdo je nese)  
  6) Vyřazená alternativa (co nebylo dovoleno uvažovat)
- C) **3 trade-offy**: „X před Y, dopad nese Z.“
- D) **2 alternativy** + cena/riziko
- E) **3 intervence** + **podmínka přezkumu** (kdy se to mění nebo ruší)

**Kontext**: Jak se to vztahuje k [scénáři]?  
**Doporučení**: Pro politické komentování, institucionální audit, digitální i nedigitální systémy.

---

## 13. BONUS: Meta-prompt (V1.0.0 – komentář-ready)
**Prompt**: Použij „Audit samozřejmostí“ na [téma] v kontextu [scénáře]. Klasifikuj A/B/C/D a aktivuj moduly dle klasifikace. Piš tvrdým rytmem. Odděl fakta a hypotézy. Nejprve přepiš zadání na systémový problém. Výstup dodrž přesně:
1) KLASIFIKACE + aktivní moduly  
2) ČERVENÁ: identifikuj volbu maskovanou za nutnost (formát „Skrytý předpoklad…“)  
3) JÁDRA+: Autorita vs. Profit / Metrika / Default / Náklady / Vyřazená alternativa  
4) ČAS: podmínka zániku (sunsetting) + termín přezkumu  
5) PRE-MORTEM: 2 cesty k obejití + 1 scénář malicious compliance  
6) PUBLIKACE: 2 věty, které rozbijí narativ „jediného možného řešení“
