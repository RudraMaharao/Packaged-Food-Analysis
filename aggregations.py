"""Six MongoDB aggregation pipelines backing the dashboard extracts."""

def count_if(field):
    return {"$sum": {"$cond": [f"${field}", 1, 0]}}

PIPELINES = {
    # 1. Coverage and transformation audit.
    "quality_overview": [
        {"$group": {"_id": None, "products": {"$sum": 1}, "raw_usable": count_if("raw_usable"),
                    "normalized_usable": count_if("normalized_usable"),
                    "any_nutrition": count_if("has_any_nutrition"),
                    "screen_eligible": count_if("hfss_screen_eligible"),
                    "flagged": {"$sum": {"$cond": [{"$eq": ["$hfss_screen_status", "Flagged"]}, 1, 0]}},
                    "mean_fields_present": {"$avg": "$nutrition_fields_present"}}},
        {"$project": {"_id": 0, "products": 1, "raw_usable": 1, "normalized_usable": 1,
                      "any_nutrition": 1, "screen_eligible": 1, "flagged": 1,
                      "mean_fields_present": {"$round": ["$mean_fields_present", 2]}}},
    ],
    # 2. Category-level nutrient landscape; averages exclude missing values.
    "category_profile": [
        {"$group": {"_id": "$category", "products": {"$sum": 1}, "with_any_nutrition": count_if("has_any_nutrition"),
                    "screen_eligible": count_if("hfss_screen_eligible"),
                    "flagged": {"$sum": {"$cond": [{"$eq": ["$hfss_screen_status", "Flagged"]}, 1, 0]}},
                    "avg_energy_kcal": {"$avg": "$energy_kcal"}, "avg_fat_g": {"$avg": "$fat_g"},
                    "avg_sugars_g": {"$avg": "$sugars_g"}, "avg_salt_g": {"$avg": "$salt_g"}}},
        {"$match": {"products": {"$gte": 20}}},
        {"$project": {"_id": 0, "category": "$_id", "products": 1, "with_any_nutrition": 1,
                      "screen_eligible": 1, "flagged": 1,
                      "flagged_pct_of_eligible": {"$cond": [{"$gt": ["$screen_eligible", 0]},
                          {"$round": [{"$multiply": [100, {"$divide": ["$flagged", "$screen_eligible"]}]}, 1]}, None]},
                      "avg_energy_kcal": {"$round": ["$avg_energy_kcal", 1]},
                      "avg_fat_g": {"$round": ["$avg_fat_g", 1]},
                      "avg_sugars_g": {"$round": ["$avg_sugars_g", 1]},
                      "avg_salt_g": {"$round": ["$avg_salt_g", 2]}}},
        {"$sort": {"products": -1}},
    ],
    # 3. Brand scorecard with a minimum denominator to limit noisy rankings.
    "brand_scorecard": [
        {"$group": {"_id": "$brand", "products": {"$sum": 1},
                    "screen_eligible": count_if("hfss_screen_eligible"),
                    "flagged": {"$sum": {"$cond": [{"$eq": ["$hfss_screen_status", "Flagged"]}, 1, 0]}},
                    "avg_energy_kcal": {"$avg": "$energy_kcal"}}},
        {"$match": {"products": {"$gte": 20}, "_id": {"$ne": "Unknown"}}},
        {"$project": {"_id": 0, "brand": "$_id", "products": 1, "screen_eligible": 1,
                      "flagged": 1, "flagged_pct_of_eligible": {"$cond": [{"$gt": ["$screen_eligible", 0]},
                          {"$round": [{"$multiply": [100, {"$divide": ["$flagged", "$screen_eligible"]}]}, 1]}, None]},
                      "avg_energy_kcal": {"$round": ["$avg_energy_kcal", 1]}}},
        {"$sort": {"products": -1}},
    ],
    # 4. Which proxy thresholds are exceeded among eligible products.
    "hfss_drivers": [
        {"$match": {"hfss_screen_eligible": True}},
        {"$project": {"driver": [{"name": "Energy", "flag": "$high_energy"},
                                  {"name": "Total fat proxy", "flag": "$high_fat_proxy"},
                                  {"name": "Total sugar proxy", "flag": "$high_sugar_proxy"},
                                  {"name": "Salt", "flag": "$high_salt"}]}},
        {"$unwind": "$driver"},
        {"$group": {"_id": "$driver.name", "evaluated": {"$sum": 1},
                    "exceeded": {"$sum": {"$cond": ["$driver.flag", 1, 0]}}}},
        {"$project": {"_id": 0, "driver": "$_id", "evaluated": 1, "exceeded": 1,
                      "exceeded_pct": {"$round": [{"$multiply": [100, {"$divide": ["$exceeded", "$evaluated"]}]}, 1]}}},
        {"$sort": {"exceeded": -1}},
    ],
    # 5. Compare existing Nutri-Score with the separate proxy screen.
    "nutriscore_screen": [
        {"$group": {"_id": {"nutriscore": "$nutriscore_grade", "screen": "$hfss_screen_status"},
                    "products": {"$sum": 1}}},
        {"$project": {"_id": 0, "nutriscore_grade": "$_id.nutriscore",
                      "hfss_screen_status": "$_id.screen", "products": 1}},
        {"$sort": {"nutriscore_grade": 1, "hfss_screen_status": 1}},
    ],
    # 6. Product-level review queue for the highest energy items in the screened subset.
    "review_queue": [
        {"$match": {"hfss_screen_status": "Flagged", "energy_kcal": {"$ne": None}}},
        {"$sort": {"energy_kcal": -1, "code": 1}},
        {"$limit": 100},
        {"$project": {"_id": 0, "code": 1, "product_name": 1, "brand": 1, "category": 1,
                      "energy_kcal": 1, "fat_g": 1, "sugars_g": 1, "salt_g": 1,
                      "high_energy": 1, "high_fat_proxy": 1, "high_sugar_proxy": 1, "high_salt": 1,
                      "quality_flags": 1}},
    ],
}
