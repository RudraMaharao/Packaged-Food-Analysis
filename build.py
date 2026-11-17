"""Build MongoDB collections and Power BI-ready exports from PackSense/OFF India CSV.

Usage: python build.py --source india_products.csv [--mongo mongodb://localhost:27017]
The exported numbers are computed, never hard-coded.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent
DB_NAME = "indian_packaged_food_nutrition"
NUMERIC = ("energy_kj", "energy_kcal", "fat", "saturated_fat", "carbohydrates", "sugars", "fiber", "proteins", "salt", "sodium")
EXPORT_FIELDS = (
    "code", "product_name", "brand", "category", "food_group", "is_beverage", "nutrition_per",
    "energy_kcal", "fat_g", "saturated_fat_g", "sugars_g", "salt_g", "protein_g", "fiber_g",
    "nutriscore_grade", "nova_group", "nutrition_fields_present", "has_any_nutrition",
    "raw_usable", "normalized_usable", "hfss_screen_eligible", "hfss_screen_status",
    "high_energy", "high_fat_proxy", "high_sugar_proxy", "high_salt", "quality_flags",
)

def num(value, lo=0, hi=None):
    try:
        n = float(value)
        if not math.isfinite(n) or n < lo or (hi is not None and n > hi):
            return None
        return n
    except (TypeError, ValueError):
        return None

def first_brand(text):
    return (text or "").split(",")[0].strip() or "Unknown"

def category(row):
    group = (row.get("pnns_groups_2") or "").strip()
    if group.lower() != "unknown" and group:
        return group
    tags = (row.get("categories_tags") or "").split("|")
    broad = {"en:foods", "en:snacks", "en:beverages", "en:plant-based-foods-and-beverages"}
    specific = [t for t in tags if t and t not in broad]
    if specific:
        return specific[-1].removeprefix("en:").replace("-", " ").title()
    return "Unclassified"

def clean(row):
    nutrients = {k: num(row.get(k)) for k in NUMERIC}
    # Basic impossible-value guards. Missing values remain missing; there is no category imputation.
    for k in ("fat", "saturated_fat", "carbohydrates", "sugars", "fiber", "proteins", "salt", "sodium"):
        if nutrients[k] is not None and nutrients[k] > 100:
            nutrients[k] = None
    kcal = nutrients["energy_kcal"]
    if kcal is None and nutrients["energy_kj"] is not None:
        kcal = nutrients["energy_kj"] / 4.184
    if kcal is not None and kcal > 900:
        kcal = None
    salt = nutrients["salt"]
    if salt is None and nutrients["sodium"] is not None:
        salt = nutrients["sodium"] * 2.5
    # OFF sodium is stored in grams per 100 g/ml; salt is also grams.
    if salt is not None and salt > 100:
        salt = None
    name = (row.get("product_name") or "").strip()
    group = (row.get("pnns_groups_1") or "").strip()
    tags = row.get("categories_tags") or ""
    beverage = group.lower() in {"beverages", "alcoholic beverages"} or "en:beverages" in tags
    basis = (row.get("nutrition_per") or "").lower()
    prepared = (row.get("nutrition_preparation") or "").lower()
    four = (kcal, nutrients["fat"], nutrients["sugars"], salt)
    # Strict screen: explicit per-100 basis, as-sold, all four proxy inputs present.
    eligible = bool(name and basis in {"100g", "100ml"} and prepared == "as_sold" and all(v is not None for v in four))
    thresholds = {"energy": 70 if beverage else 250, "fat": 1.5 if beverage else 4.2,
                  "sugar": 2 if beverage else 3, "salt": 0.175 if beverage else 0.625}
    flags = {
        "high_energy": bool(eligible and kcal > thresholds["energy"]),
        "high_fat_proxy": bool(eligible and nutrients["fat"] > thresholds["fat"]),
        "high_sugar_proxy": bool(eligible and nutrients["sugars"] > thresholds["sugar"]),
        "high_salt": bool(eligible and salt > thresholds["salt"]),
    }
    status = "Insufficient data"
    if eligible:
        status = "Flagged" if any(flags.values()) else "Within proxy thresholds"
    raw_count = sum(row.get(k, "") != "" for k in ("energy_kcal", "fat", "sugars", "salt", "proteins", "fiber"))
    normalized_count = sum(v is not None for v in (kcal, nutrients["fat"], nutrients["sugars"], salt, nutrients["proteins"], nutrients["fiber"]))
    return {
        "code": row["code"], "product_name": name or "Unnamed product", "brand": first_brand(row.get("brands")),
        "category": category(row), "food_group": group or "Unknown", "is_beverage": beverage,
        "nutrition_per": basis or "Unknown", "energy_kcal": kcal, "fat_g": nutrients["fat"],
        "saturated_fat_g": nutrients["saturated_fat"], "sugars_g": nutrients["sugars"],
        "salt_g": salt, "protein_g": nutrients["proteins"], "fiber_g": nutrients["fiber"],
        "nutriscore_grade": (row.get("nutriscore_grade") or "unknown").upper(),
        "nova_group": int(float(row["nova_group"])) if row.get("nova_group") else None,
        "nutrition_fields_present": normalized_count, "has_any_nutrition": normalized_count > 0,
        "raw_usable": bool(name and raw_count >= 3), "normalized_usable": bool(name and normalized_count >= 3),
        "hfss_screen_eligible": eligible, "hfss_screen_status": status, **flags,
        "quality_flags": int(row.get("open_error_flags") or 0) + int(row.get("open_warning_flags") or 0),
    }

def write_csv(path, docs, fields=None):
    docs = list(docs)
    fields = list(fields or (docs[0].keys() if docs else []))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(docs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "india_products.csv"))
    ap.add_argument("--mongo", default="mongodb://localhost:27017")
    args = ap.parse_args()
    with open(args.source, newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    codes = [r["code"] for r in raw]
    if len(codes) != len(set(codes)):
        raise ValueError("Source has duplicate barcodes")
    cleaned = [clean(row) for row in raw]
    client = MongoClient(args.mongo, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[DB_NAME]
    db.raw_products.drop()
    db.products.drop()
    db.raw_products.insert_many(raw, ordered=False)
    db.products.insert_many(cleaned, ordered=False)
    db.raw_products.create_index("code", unique=True)
    db.products.create_index("code", unique=True)
    db.products.create_index([("category", 1), ("hfss_screen_status", 1)])
    db.products.create_index("brand")
    write_csv(ROOT / "dashboard_products.csv", cleaned, EXPORT_FIELDS)
    from aggregations import PIPELINES
    agg_dir = ROOT / "aggregates"
    agg_dir.mkdir(exist_ok=True)
    summary = {}
    for name, pipeline in PIPELINES.items():
        result = list(db.products.aggregate(pipeline, allowDiskUse=True))
        for doc in result:
            doc.pop("_id", None)
        write_csv(agg_dir / f"{name}.csv", result)
        summary[name] = len(result)
    count = len(cleaned)
    metrics = {"source_rows": count, "raw_usable": sum(x["raw_usable"] for x in cleaned),
               "normalized_usable": sum(x["normalized_usable"] for x in cleaned),
               "hfss_screen_eligible": sum(x["hfss_screen_eligible"] for x in cleaned),
               "hfss_flagged": sum(x["hfss_screen_status"] == "Flagged" for x in cleaned),
               "nutrition_missing": sum(not x["has_any_nutrition"] for x in cleaned),
               "mongo_database": DB_NAME, "aggregation_rows": summary}
    metrics["raw_usable_pct"] = round(100 * metrics["raw_usable"] / count, 1)
    metrics["normalized_usable_pct"] = round(100 * metrics["normalized_usable"] / count, 1)
    metrics["hfss_eligible_pct"] = round(100 * metrics["hfss_screen_eligible"] / count, 1)
    (ROOT / "run_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
