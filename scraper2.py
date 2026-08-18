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
  Am besten regelmäßig prüfen, ob noch Ergebnisse kommen, und Selektoren
  ggf. über die Browser-DevTools neu ermitteln (Rechtsklick auf ein
  Produkt -> Untersuchen).

ROBUSTHEIT / TIMEOUTS:
Frühere Version konnte unbegrenzt hängen bleiben, z.B. wenn AliExpress
ein Cookie-Banner, ein Captcha oder eine Standort-Abfrage zeigt, auf die
das Skript nie reagiert. Jetzt gilt für jedes Keyword eine harte
Zeitgrenze (PER_KEYWORD_TIMEOUT_SECONDS) über einen separaten Thread —
läuft die Zeit ab, wird das Keyword abgebrochen und es geht mit dem
nächsten weiter, statt den ganzen Lauf zu blockieren. Zusätzlich gibt es
eine Gesamtzeit-Bremse (MAX_TOTAL_SECONDS) für den kompletten Durchlauf.
"""

import time
import random
import concurrent.futures
from dataclasses import dataclass
from typing import List

from config import SEARCH_KEYWORDS, REQUEST_DELAY_SECONDS, USER_AGENT

# Harte Zeitgrenze pro Keyword (Sekunden). Wenn eine Suche länger braucht
# (z.B. weil AliExpress hängt oder ein Captcha zeigt), wird abgebrochen.
PER_KEYWORD_TIMEOUT_SECONDS = 45

# Gesamte Zeitgrenze für den kompletten täglichen Lauf (Sekunden).
# Sicherheitsnetz, falls z.B. sehr viele Keywords konfiguriert sind.
MAX_TOTAL_SECONDS = 600  # 10 Minuten

# Playwright-Standard-Timeout für alle Aktionen (Klicks, Selektoren, etc.)
PLAYWRIGHT_DEFAULT_TIMEOUT_MS = 15000


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


def _fetch_bestsellers_for_keyword_impl(keyword: str, limit: int = 20) -> List[RawProduct]:
    """
    Eigentliche Scraping-Logik für ein Keyword. Wird von
    fetch_bestsellers_for_keyword() mit einem harten Timeout umschlossen.
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
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            # Gilt für ALLE folgenden Aktionen (Klicks, wait_for_selector, ...).
            # Verhindert, dass irgendein einzelner Schritt endlos wartet.
            context.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT_MS)

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
        finally:
            # Browser IMMER schließen, auch wenn oben ein Fehler passiert ist.
            browser.close()

    return results


def fetch_bestsellers_for_keyword(keyword: str, limit: int = 20) -> List[RawProduct]:
    """
    Wrapper mit harter Zeitgrenze: läuft die eigentliche Scraping-Funktion
    in einem separaten Thread. Überschreitet sie PER_KEYWORD_TIMEOUT_SECONDS,
    wird abgebrochen und eine leere Liste zurückgegeben, statt den ganzen
    Lauf zu blockieren.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch_bestsellers_for_keyword_impl, keyword, limit)
        try:
            return future.result(timeout=PER_KEYWORD_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            print(
                f"[Warnung] Keyword '{keyword}' hat {PER_KEYWORD_TIMEOUT_SECONDS}s "
                "überschritten (evtl. Captcha/Cookie-Banner/Blockade) - "
                "wird abgebrochen, weiter mit dem nächsten Keyword."
            )
            # Der Thread läuft im Hintergrund evtl. noch kurz weiter, wird
            # aber durch das Prozessende bzw. das Job-Timeout in GitHub
            # Actions spätestens beendet.
            return []


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

    Bricht komplett ab, sobald MAX_TOTAL_SECONDS überschritten ist, auch
    wenn noch nicht alle Keywords durch sind - dann wird einfach mit dem
    ausgewertet, was bis dahin gefunden wurde.
    """
    all_products: List[RawProduct] = []
    start_time = time.monotonic()

    keywords = SEARCH_KEYWORDS if SEARCH_KEYWORDS else [""]
    for keyword in keywords:
        elapsed = time.monotonic() - start_time
        if elapsed > MAX_TOTAL_SECONDS:
            print(
                f"[Warnung] Gesamtzeitlimit von {MAX_TOTAL_SECONDS}s erreicht - "
                f"breche ab, {len(all_products)} Produkte bisher gefunden."
            )
            break

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
