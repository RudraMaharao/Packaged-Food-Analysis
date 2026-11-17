"""Independent consistency checks for the local database and dashboard export."""
import csv
import hashlib
import json
from pathlib import Path

from pymongo import MongoClient

root = Path(__file__).resolve().parent
source = root / "india_products.csv"
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
assert source_sha == "9007b7a48fe9bc129e6a90a6fc7dfb4dfdcb6a72f53b3a3aabc74eda0d5d1951", source_sha
with source.open(newline="", encoding="utf-8-sig") as f:
    raw = list(csv.DictReader(f))
with (root / "dashboard_products.csv").open(newline="", encoding="utf-8-sig") as f:
    export = list(csv.DictReader(f))
metrics = json.loads((root / "run_metrics.json").read_text())
assert len(raw) == len(export) == metrics["source_rows"] == 25209
raw_codes = {r["code"] for r in raw}
export_codes = {r["code"] for r in export}
assert len(raw_codes) == len(export_codes) == 25209 and raw_codes == export_codes
assert sum(r["raw_usable"] == "True" for r in export) == metrics["raw_usable"]
assert sum(r["normalized_usable"] == "True" for r in export) == metrics["normalized_usable"]
assert sum(r["hfss_screen_eligible"] == "True" for r in export) == metrics["hfss_screen_eligible"]
assert sum(r["hfss_screen_status"] == "Flagged" for r in export) == metrics["hfss_flagged"]
for row in export:
    eligible = row["hfss_screen_eligible"] == "True"
    flags = any(row[k] == "True" for k in ("high_energy", "high_fat_proxy", "high_sugar_proxy", "high_salt"))
    assert (row["hfss_screen_status"] == "Flagged") == (eligible and flags)
    if not eligible:
        assert row["hfss_screen_status"] == "Insufficient data"

db = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)["indian_packaged_food_nutrition"]
assert db.raw_products.count_documents({}) == db.products.count_documents({}) == 25209
assert db.products.count_documents({"hfss_screen_status": "Flagged"}) == metrics["hfss_flagged"]
with (root / "aggregates" / "quality_overview.csv").open(newline="", encoding="utf-8-sig") as f:
    overview = next(csv.DictReader(f))
assert int(overview["products"]) == 25209
assert int(overview["screen_eligible"]) == metrics["hfss_screen_eligible"]
assert int(overview["flagged"]) == metrics["hfss_flagged"]
print("PASS: source checksum, unique IDs, export parity, screen invariants, MongoDB counts, and aggregate totals")
