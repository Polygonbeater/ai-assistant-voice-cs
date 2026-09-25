"""Inteligentní zpravodajský a webový modul pro Polygon Beater AI."""

from __future__ import annotations
import logging
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import trafilatura
import lxml.html

logger = logging.getLogger(__name__)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)


USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _fetch_article_text(url: str, max_chars: int = 850) -> str:
    """Stáhne a očistí tělo článku z URL pomocí trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        if extracted:
            # Kontrola proti starým archivům (pokud text obsahuje staré roky 2010-2023 u dotazu na zprávy)
            old_years = [str(y) for y in range(2010, 2024)]
            first_500 = extracted[:500]
            if any(f".{y}" in first_500 or f" {y}" in first_500 for y in old_years):
                logger.warning("Článek %s vyřazen (detekován archivní rok).", url)
                return ""
            return extracted.strip()[:max_chars]
    except Exception as exc:
        logger.debug("Chyba při stahování %s: %s", url, exc)
    return ""


def _fetch_ct24_live() -> list[dict]:
    """Přímo vytáhne aktuální hlavní události z portálu ČT24."""
    url = "https://ct24.ceskatelevize.cz/tema/hlavni-udalosti-90196"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=7) as resp:
            html = resp.read()
        doc = lxml.html.fromstring(html)
        items = []
        for a in doc.xpath('//a[starts-with(@href, "/clanek/")]'):
            href = a.get("href", "")
            title = a.text_content().strip()
            # Filtrovat drobné navigační popisky
            if len(title) > 25 and not any(x["url"].endswith(href) for x in items):
                full_url = "https://ct24.ceskatelevize.cz" + href if href.startswith("/") else href
                items.append({"title": title, "url": full_url, "source": "ČT24 Živě"})
        return items[:2]
    except Exception as exc:
        logger.warning("Přímé načtení ČT24 selhalo: %s", exc)
        return []


def _fetch_google_news_rss(query: str = "") -> list[dict]:
    """Vrátí 100% čerstvé zprávy z Google News RSS (Česká republika)."""
    try:
        if query and not any(k in query.lower() for k in ("zprávy", "události", "hlavní", "dnes")):
            encoded = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=cs&gl=CZ&ceid=CZ:cs"
        else:
            rss_url = "https://news.google.com/rss?hl=cs&gl=CZ&ceid=CZ:cs"

        req = urllib.request.Request(rss_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=7) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall(".//item")[:5]:
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            pub_date = item.findtext("pubDate") or ""
            source = item.find("source")
            src_name = source.text if source is not None else "Zpravodajství"
            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": src_name,
                    "date": pub_date
                })
        return items
    except Exception as exc:
        logger.warning("Google News RSS selhalo: %s", exc)
        return []


def search_web_context(query: str, *, max_articles: int = 2, timeout: float = 10.0) -> str:
    """Chytrý router pro zprávy i obecné vyhledávání na webu."""
    clean_query = query.strip().rstrip(".?!")
    if not clean_query:
        return ""

    q_lower = clean_query.lower()
    is_news_query = any(k in q_lower for k in (
        "čt24", "čt 24", "udalosti", "události", "zprávy", "zpravy", 
        "novinky", "dnes", "aktuální", "co se děje", "souhrn"
    ))

    articles_to_fetch = []

    # 1. Pokud dotaz cílí na ČT24 nebo Hlavní události, priorita má živý feed ČT24
    if "čt" in q_lower or "ct24" in q_lower or "hlavní události" in q_lower:
        ct_items = _fetch_ct24_live()
        articles_to_fetch.extend(ct_items)

    # 2. Doplnění o čerstvé zprávy z Google News RSS
    if is_news_query and len(articles_to_fetch) < max_articles:
        news_items = _fetch_google_news_rss(clean_query)
        for it in news_items:
            if not any(a["title"] == it["title"] for a in articles_to_fetch):
                articles_to_fetch.append(it)

    # 3. Fallback na vyhledávač (DDGS), pokud nejde o obecné zprávy
    if not articles_to_fetch:
        try:
            from ddgs import DDGS
            with DDGS() as client:
                ddg_items = list(client.news(clean_query, region="cz-cs", timelimit="d", max_results=max_articles))
                if not ddg_items:
                    ddg_items = list(client.text(clean_query, region="cz-cs", max_results=max_articles))
                for item in ddg_items:
                    url = item.get("href") or item.get("url")
                    title = item.get("title", "")
                    if url and title:
                        articles_to_fetch.append({"title": title, "url": url, "source": "Web"})
        except Exception as exc:
            logger.warning("DDGS fallback selhal: %s", exc)

    if not articles_to_fetch:
        return "Nepodařilo se nalézt žádné aktuální zprávy k tomuto tématu."

    # Paralelní stažení plných textů článků
    docs = []
    with ThreadPoolExecutor(max_workers=max_articles) as executor:
        future_map = {
            executor.submit(_fetch_article_text, it["url"]): it
            for it in articles_to_fetch[:max_articles]
        }
        for future in as_completed(future_map, timeout=timeout):
            item = future_map[future]
            try:
                full_text = future.result()
            except Exception:
                full_text = ""

            content = full_text if full_text else item.get("title", "")
            docs.append(
                f"### Zdroj: {item['title']} ({item.get('source', 'Zpravodajství')})\n"
                f"URL: {item['url']}\n"
                f"Obsah zprávy:\n{content}\n"
            )

    if not docs:
        return "Nepodařilo se načíst obsah aktuálních článků."

    header = (
        "AKTUÁLNÍ ZPRAVODAJSTVÍ Z INTERNETU (reálná dnešní data):\n"
        "- Shrnuj fakta přesně a věcně.\n"
        "- U každého klíčového bodu uveď klikatelný odkaz ve formátu [Zdroj](URL).\n"
        "- Na konec zprávy přidej přehled '### Použité zdroje'.\n\n"
    )
    return header + "\n---\n".join(docs)
