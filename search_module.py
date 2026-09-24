import logging
from duckduckgo_search import DDGS

def vyhledej_na_internetu(dotaz):
    try:
        logging.info(f"Hledám na internetu: {dotaz}")
        with DDGS() as ddgs:
            vysledky = list(ddgs.text(dotaz, max_results=3))
        if not vysledky:
            return "Nenašel jsem žádné relevantní informace."
            
        kontext = "Aktuální informace:\n"
        for v in vysledky:
            kontext += f"- {v.get('title', '')}: {v.get('body', '')}\n"
        return kontext
    except Exception as e:
        logging.error(f"Chyba při webovém vyhledávání: {e}")
        return "Chyba: Webové vyhledávání je momentálně nedostupné."

def vyhledej_zpravy(dotaz="aktuální události"):
    try:
        logging.info(f"Stahuji zprávy a bezpečnostní kontext pro: {dotaz}")
        upraveny_dotaz = f"{dotaz} zprávy analýza bezpečnost"
        with DDGS() as ddgs:
            vysledky = list(ddgs.news(upraveny_dotaz, max_results=5))
            if not vysledky:
                vysledky = list(ddgs.text(dotaz, max_results=4))
                
        if not vysledky:
            return "Nenašel jsem žádné aktuální zprávy ani ověřené zdroje."
            
        kontext = "Aktuální zprávy a ověřené zdroje (Tier A/B):\n"
        for v in vysledky:
            zdroj = v.get('source') or v.get('title', '').split('-')[-1].strip()
            kontext += f"- {v.get('title', '')} (Zdroj: {zdroj}): {v.get('body', '')}\n"
        return kontext
    except Exception as e:
        logging.error(f"Chyba při stahování zpráv: {e}")
        return "Chyba: Zpravodajský modul je momentálně nedostupný."
