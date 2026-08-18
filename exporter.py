"""
Exportiert fertige Listings als CSV im eBay-File-Exchange-Format und
lädt Produktbilder lokal herunter.

Hinweis zum CSV-Format: eBay File Exchange erwartet bestimmte Pflichtspalten.
Die Spaltennamen unten decken die Basics ab (Fixed-Price-Listing). Vor dem
ersten echten Upload unbedingt in deinem eBay Seller Hub unter
"Datei-Download/-Upload" die aktuelle Beispiel-CSV herunterladen und die
Spalten abgleichen, da eBay das Format gelegentlich anpasst.
"""

import csv
import json
import os
from datetime import datetime, timezone
from typing import List

import requests

from processor import ListingProduct
from config import OUTPUT_DIR, CSV_FILENAME, JSON_FILENAME, IMAGES_SUBDIR


CSV_HEADERS = [
    "Action(SiteID=Germany|Country=DE|Currency=EUR|Version=1193)",
    "Category",
    "Title",
    "Description",
    "ConditionID",
    "PicURL",
    "Format",
    "Duration",
    "StartPrice",
    "BuyItNowPrice",
    "Quantity",
    "PaymentMethods",
    "PayPalEmailAddress",
    "ShippingType",
    "ShippingService-1:Option",
    "ShippingService-1:Cost",
    "Location",
]


def download_images(product: ListingProduct, index: int, images_dir: str) -> List[str]:
    local_paths = []
    for i, url in enumerate(product.image_urls):
        if not url:
            continue
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            ext = ".jpg"
            filename = f"produkt_{index}_{i}{ext}"
            filepath = os.path.join(images_dir, filename)
            with open(filepath, "wb") as f:
                f.write(response.content)
            local_paths.append(filepath)
        except Exception as exc:
            print(f"[Warnung] Bild-Download fehlgeschlagen für {url}: {exc}")
    return local_paths


def export_all(products: List[ListingProduct]) -> dict:
    """
    Lädt Bilder herunter und schreibt sowohl die eBay-CSV als auch die
    products.json für die mobile Webseite. Gibt Pfade zu beiden zurück.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    images_dir = os.path.join(OUTPUT_DIR, IMAGES_SUBDIR)
    os.makedirs(images_dir, exist_ok=True)

    all_local_images: List[List[str]] = []
    csv_path = os.path.join(OUTPUT_DIR, CSV_FILENAME)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

        for idx, product in enumerate(products, start=1):
            local_images = download_images(product, idx, images_dir)
            all_local_images.append(local_images)

            writer.writerow([
                "Add",
                "",  # Category: eBay-Kategorie-ID hier eintragen/anpassen
                product.title,
                product.description,
                "1000",  # 1000 = Neu
                product.image_urls[0] if product.image_urls else "",
                "FixedPrice",
                "GTC",
                product.sell_price_eur,
                product.sell_price_eur,
                1,
                "PayPal",
                "",  # Deine PayPal-Adresse eintragen
                "Flat",
                "Standard Versand",
                0,
                "DE",
            ])

    json_path = export_to_json(products, all_local_images)

    return {"csv_path": csv_path, "json_path": json_path}


def export_to_json(products: List[ListingProduct], local_image_paths: List[List[str]]) -> str:
    """
    Schreibt eine products.json, die von der mobilen Webseite (docs/index.html)
    geladen und angezeigt wird.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, JSON_FILENAME)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "products": [],
    }

    for product, images in zip(products, local_image_paths):
        # relative Pfade fürs Web (ab docs/ Ordner)
        web_images = [
            os.path.relpath(p, OUTPUT_DIR).replace(os.sep, "/") for p in images
        ]
        data["products"].append({
            "title": product.title,
            "description": product.description,
            "sell_price_eur": product.sell_price_eur,
            "cost_price_eur": product.cost_price_eur,
            "source_url": product.source_url,
            "images": web_images,
        })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return json_path
