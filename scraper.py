"""
Scraper für AliExpress Bestseller-/Trend-Produkte.

WICHTIG:
- AliExpress hat keine offizielle Public API für Einzelverkäufer. Dieses
  Modul nutzt Browser-Automatisierung (Playwright), weil die Seite ihre
  Inhalte per JavaScript nachlädt.
- Automatisiertes Scraping verstößt gegen die Nutzungsbedingungen von
  AliExpress. Das Skript kann jederzeit durch Layout-Änderungen, Captchas
  oder IP-Sperren aufhören zu funktionieren. Nutzung auf eigenes Risiko.
- Die Selektoren (CSS-Klassen) unten sind ein Ausgangspunkt und müssen
  sehr wahrscheinlich angepasst werden, sobald AliExpress sein HTML ändert.
  Am besten regelmäßig mit `python scraper.py --debug` prüfen, ob noch
  Ergebnisse kommen, und Selektoren ggf. über die Browser-DevTools neu
  ermitteln (Rechtsklick auf ein Produkt -> Untersuchen).
"""

import time
import random
from dataclasses import dataclass, field
from typing import List

from config import SEARCH_KEYWORDS, REQUEST_DELAY_SECONDS, USER_AGENT


@dataclass
class RawProduct:
    title: str
    price: float
    currency: str
    image_urls: List[str]
    product_url: str
    orders_count: int = 0
    rating: float = 0.0
    description_html: str = ""
    keyword: str = ""


def _build_search_url(keyword: str) -> str:
    # sortType=orders_desc sortiert nach Bestellzahl -> Bestseller
    query = keyword.replace(" ", "+")
    return f"https://www.aliexpress.com/wholesale?SearchText={query}&SortType=orders_desc"


def fetch_bestsellers_for_keyword(keyword: str, limit: int = 20) -> List[RawProduct]:
    """
    Lädt eine Suchergebnisseite und extrahiert die obersten Bestseller.
    Nutzt Playwright, weil AliExpress Inhalte dynamisch nachlädt.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright ist nicht installiert. Bitte 'pip install playwright' "
            "und danach 'playwright install chromium' ausführen."
        ) from exc

    url = _build_search_url(keyword)
    results: List[RawProduct] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_timeout(4000)  # Zeit zum Nachladen der Produktkarten geben

        # HINWEIS: Diese Selektoren sind ein Startpunkt und müssen ggf.
        # über die Browser-DevTools an das aktuelle AliExpress-HTML
        # angepasst werden.
        cards = page.query_selector_all("[class*='SearchProductFeed_ProductCard']")

        for card in cards[:limit]:
            try:
                title_el = card.query_selector("[class*='multi--titleText']")
                price_el = card.query_selector("[class*='multi--price-sale']")
                img_el = card.query_selector("img")
                link_el = card.query_selector("a")
                orders_el = card.query_selector("[class*='multi--trade']")

                if not (title_el and price_el and link_el):
                    continue

                title = title_el.inner_text().strip()
                price_text = price_el.inner_text().strip()
                price = _parse_price(price_text)
                image_url = img_el.get_attribute("src") if img_el else ""
                product_url = link_el.get_attribute("href") or ""
                if product_url.startswith("//"):
                    product_url = "https:" + product_url

                orders_text = orders_el.inner_text() if orders_el else "0"
                orders_count = _parse_orders(orders_text)

                results.append(
                    RawProduct(
                        title=title,
                        price=price,
                        currency="EUR",
                        image_urls=[image_url] if image_url else [],
                        product_url=product_url,
                        orders_count=orders_count,
                        keyword=keyword,
                    )
                )
            except Exception:
                # Einzelne kaputte Karten überspringen statt ganzen Lauf abzubrechen
                continue

        browser.close()

    return results


def _parse_price(text: str) -> float:
    cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_orders(text: str) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def fetch_daily_bestsellers(total_needed: int) -> List[RawProduct]:
    """
    Geht alle konfigurierten Keywords durch, sammelt Bestseller und gibt
    die nach Bestellzahl sortierten Top-Produkte zurück.
    """
    all_products: List[RawProduct] = []

    keywords = SEARCH_KEYWORDS if SEARCH_KEYWORDS else [""]
    for keyword in keywords:
        try:
            products = fetch_bestsellers_for_keyword(keyword)
            all_products.extend(products)
        except Exception as exc:
            print(f"[Warnung] Keyword '{keyword}' fehlgeschlagen: {exc}")
        time.sleep(REQUEST_DELAY_SECONDS + random.uniform(0, 1.5))

    all_products.sort(key=lambda p: p.orders_count, reverse=True)
    return all_products[:total_needed]


if __name__ == "__main__":
    found = fetch_daily_bestsellers(10)
    for p in found:
        print(f"{p.orders_count:>6} Bestellungen | {p.price} {p.currency} | {p.title[:60]}")
