"""
Wandelt rohe AliExpress-Produktdaten in fertige eBay-Listing-Daten um:
- SEO-freundlicher Titel (eBay erlaubt max. 80 Zeichen)
- Umformulierte Beschreibung (wichtig: keine 1:1-Kopie -> Duplicate Content
  und eBay-Richtlinien)
- Verkaufspreis inkl. Marge, eBay-Gebühren und Zahlungsgebühren
"""

import re
from dataclasses import dataclass
from typing import List

from scraper import RawProduct
from config import (
    MARGIN_PERCENT,
    EBAY_FEE_PERCENT,
    PAYMENT_FEE_PERCENT,
    PAYMENT_FEE_FIXED_EUR,
    ESTIMATED_SHIPPING_EUR,
)

EBAY_TITLE_MAX_LEN = 80

# Wörter, die AliExpress-Titel oft aufblähen und für eBay entfernt werden sollten
NOISE_WORDS = [
    "free shipping", "hot sale", "new arrival", "high quality",
    "wholesale", "dropshipping", "aliexpress", "1pcs", "2024", "2025", "2026",
]


@dataclass
class ListingProduct:
    title: str
    description: str
    sell_price_eur: float
    cost_price_eur: float
    image_urls: List[str]
    source_url: str
    category_hint: str


def clean_title(raw_title: str) -> str:
    title = raw_title
    for noise in NOISE_WORDS:
        title = re.sub(noise, "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" ,-|")
    if len(title) > EBAY_TITLE_MAX_LEN:
        title = title[:EBAY_TITLE_MAX_LEN].rsplit(" ", 1)[0]
    return title


def generate_description(product_title: str, keyword: str) -> str:
    """
    Erstellt eine einfache, umformulierte Beschreibung auf Basis von Titel
    und Kategorie. Das ist bewusst simpel/template-basiert, damit das Skript
    ohne externe KI-API läuft. Für bessere Texte kann hier optional ein
    Aufruf an die Anthropic API (claude-sonnet-4-6) ergänzt werden, der aus
    dem AliExpress-Originaltext eine echte Neuformulierung erzeugt.
    """
    return (
        f"{product_title}\n\n"
        f"Praktisches Produkt aus dem Bereich {keyword or 'Alltag'}. "
        f"Sorgfältig ausgewählt für gute Qualität und zuverlässigen Versand.\n\n"
        f"- Schneller, sicherer Versand\n"
        f"- Sorgfältig verpackt\n"
        f"- Bei Fragen jederzeit gerne Kontakt aufnehmen\n\n"
        f"Hinweis: Lieferzeit kann je nach Lagerort variieren."
    )


def calculate_sell_price(cost_price_eur: float) -> float:
    price_with_margin = cost_price_eur * (1 + MARGIN_PERCENT / 100)
    price_with_margin += ESTIMATED_SHIPPING_EUR

    # Preis so hochrechnen, dass nach Abzug von eBay- und Zahlungsgebühren
    # die gewünschte Marge übrig bleibt
    fee_fraction = (EBAY_FEE_PERCENT + PAYMENT_FEE_PERCENT) / 100
    if fee_fraction >= 1:
        raise ValueError("Gebührensumme darf nicht >= 100% sein")

    final_price = (price_with_margin + PAYMENT_FEE_FIXED_EUR) / (1 - fee_fraction)
    return round(final_price, 2)


def process_product(raw: RawProduct) -> ListingProduct:
    title = clean_title(raw.title)
    description = generate_description(title, raw.keyword)
    sell_price = calculate_sell_price(raw.price)

    return ListingProduct(
        title=title,
        description=description,
        sell_price_eur=sell_price,
        cost_price_eur=raw.price,
        image_urls=raw.image_urls,
        source_url=raw.product_url,
        category_hint=raw.keyword,
    )


def process_all(raw_products: List[RawProduct]) -> List[ListingProduct]:
    return [process_product(p) for p in raw_products]
