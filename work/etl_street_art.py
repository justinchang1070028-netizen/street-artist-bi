# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""把 data/raw_street_art.csv 轉成乾淨的 work/clean_street_art.csv。"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_street_art.csv"
OUT = ROOT / "work" / "clean_street_art.csv"

COLUMNS = ["year", "county", "venue_count", "music_count",
           "perform_count", "visual_count", "total_count"]
NUMERIC = [c for c in COLUMNS if c != "county"]
NATIONAL = "全國總計"


def main() -> None:
    with RAW.open(encoding="utf-8-sig", newline="") as f:
        lines = f.read().splitlines()

    # 前 3 行是報表標題、製表日期、單位；第 4 行是原始欄位名稱
    reader = csv.reader(lines[4:])
    rows = []
    for raw in reader:
        if not raw:
            continue
        if len(raw) != len(COLUMNS):
            sys.exit(f"欄位數不對：{raw}")
        row = dict(zip(COLUMNS, (v.strip() for v in raw)))
        for c in NUMERIC:
            row[c] = int(row[c])
        rows.append(row)

    errors = []

    # 驗證 1：每一列的三類人數加總 = 合計
    for r in rows:
        s = r["music_count"] + r["perform_count"] + r["visual_count"]
        if s != r["total_count"]:
            errors.append(f"{r['year']} {r['county']}：三類加總 {s} ≠ 合計 {r['total_count']}")

    # 驗證 2：各縣市加總 = 全國總計（排除前先核對）
    for year in sorted({r["year"] for r in rows}):
        national = [r for r in rows if r["year"] == year and r["county"] == NATIONAL]
        if len(national) != 1:
            errors.append(f"{year}：找不到唯一的「{NATIONAL}」列")
            continue
        counties = [r for r in rows if r["year"] == year and r["county"] != NATIONAL]
        for c in NUMERIC[1:]:
            s = sum(r[c] for r in counties)
            if s != national[0][c]:
                errors.append(f"{year} {c}：縣市加總 {s} ≠ 全國總計 {national[0][c]}")

    if errors:
        sys.exit("驗證失敗：\n" + "\n".join(errors))

    clean = [r for r in rows if r["county"] != NATIONAL]
    clean.sort(key=lambda r: (r["year"], r["county"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(clean)

    print(f"✅ 驗證通過，輸出 {len(clean)} 列 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
