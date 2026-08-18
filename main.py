"""
Hauptskript: einmal ausführen -> holt Bestseller, bereitet sie auf,
exportiert eBay-CSV + Bilder.

Nutzung:
    python main.py

Für den täglichen Automatik-Lauf kannst du das z.B. per Windows-
Aufgabenplanung (Task Scheduler) oder cron (Linux/Mac) einmal täglich
starten lassen.
"""

from config import PRODUCTS_PER_RUN
from scraper import fetch_daily_bestsellers
from processor import process_all
from exporter import export_all


def run():
    print(f"Suche {PRODUCTS_PER_RUN} Bestseller-Produkte...")
    raw_products = fetch_daily_bestsellers(PRODUCTS_PER_RUN)

    if not raw_products:
        print(
            "Keine Produkte gefunden. Möglliche Ursachen: AliExpress hat "
            "Layout/Selektoren geändert, IP wurde geblockt, oder Captcha "
            "kam dazwischen. Siehe README für Troubleshooting."
        )
        return

    print(f"{len(raw_products)} Produkte gefunden. Verarbeite...")
    listings = process_all(raw_products)

    print("Exportiere CSV, Bilder und JSON für die Web-App...")
    paths = export_all(listings)

    print(f"\nFertig! {len(listings)} Produkte vorbereitet.")
    print(f"CSV zum Hochladen: {paths['csv_path']}")
    print(f"JSON für die Handy-Seite: {paths['json_path']}")
    print(
        "\nNächster Schritt: docs/ nach GitHub pushen (macht die GitHub "
        "Action automatisch), dann auf der Handy-Seite ansehen und CSV "
        "in eBay Seller Hub unter 'Zeitplan/Datei-Upload' hochladen."
    )


if __name__ == "__main__":
    run()
