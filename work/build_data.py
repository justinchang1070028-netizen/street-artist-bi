# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""把 work/ 的乾淨資料轉成網頁可直接載入的 docs/data.js。

- rawData   ：年資料（work/clean_street_art.csv）
- venueData ：場地名冊（work/clean_venues.csv）
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YEARLY = ROOT / "work" / "clean_street_art.csv"
VENUES = ROOT / "work" / "clean_venues.csv"
OUT = ROOT / "docs" / "data.js"

YEARLY_INT = {"year", "licences", "venues"}
YEARLY_FLOAT = {"licences_per_venue", "licences_index", "licences_yoy_pct", "venues_yoy_pct"}
VENUE_INT = {"perform", "visual", "craft", "restricted"}


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def convert(rows: list[dict], ints: set, floats: set = frozenset()) -> list[dict]:
    for r in rows:
        for k, v in r.items():
            if k in ints:
                r[k] = int(v)
            elif k in floats:
                r[k] = float(v) if v != "" else None
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 主控台預設不是 UTF-8
    yearly = convert(read(YEARLY), YEARLY_INT, YEARLY_FLOAT)
    venues = convert(read(VENUES), VENUE_INT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    dump = lambda x: json.dumps(x, ensure_ascii=False, indent=2)
    OUT.write_text(
        "// 由 work/build_data.py 自動產生，請勿手動修改\n"
        f"const rawData = {dump(yearly)};\n\n"
        f"const venueData = {dump(venues)};\n",
        encoding="utf-8",
    )
    print(f"✅ rawData {len(yearly)} 筆、venueData {len(venues)} 筆 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
