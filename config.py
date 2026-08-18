"""
Zentrale Konfiguration für das Dropshipping-Tool.
Hier alle Werte an deine Situation anpassen.
"""

# Wie viele Produkte pro Lauf vorbereitet werden sollen
PRODUCTS_PER_RUN = 10

# Kategorien / Keywords, aus denen Bestseller gezogen werden.
# Leer lassen ("") für "alle Kategorien" (liefert breiteren Trend-Mix).
SEARCH_KEYWORDS = [
    "gadgets",
    "home",
    "fitness",
    "kitchen",
    "pet supplies",
]

# --- Preiskalkulation ---
# Deine Ziel-Marge in Prozent auf den Einkaufspreis
MARGIN_PERCENT = 45

# eBay-Verkaufsprovision (variiert je Kategorie, Durchschnitt ansetzen)
EBAY_FEE_PERCENT = 12.5

# Fixe Zahlungsabwicklungsgebühr (PayPal/eBay Payments), grob geschätzt
PAYMENT_FEE_PERCENT = 2.9
PAYMENT_FEE_FIXED_EUR = 0.35

# Versandkosten, die du selbst einplanst (falls nicht "kostenloser Versand"
# vom Lieferanten inkludiert ist)
ESTIMATED_SHIPPING_EUR = 0.0

# --- Ausgabe ---
# docs/ wird von GitHub Pages als Webseite ausgeliefert
OUTPUT_DIR = "docs/data"
CSV_FILENAME = "ebay_upload.csv"
JSON_FILENAME = "products.json"
IMAGES_SUBDIR = "images"

# --- Scraping-Verhalten ---
# Wartezeit zwischen Requests, um nicht sofort geblockt zu werden (Sekunden)
REQUEST_DELAY_SECONDS = 3.0

# User-Agent für Requests (reduziert Blockierungswahrscheinlichkeit etwas,
# garantiert aber nichts)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
