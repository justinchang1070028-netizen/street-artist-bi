# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""把 work/clean_street_art.csv 轉成網頁可直接載入的 docs/data.js。"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "work" / "clean_street_art.csv"
OUT = ROOT / "docs" / "data.js"


def main() -> None:
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # county 以外的欄位都是整數
    for r in rows:
        for k, v in r.items():
            if k != "county":
                r[k] = int(v)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(rows, ensure_ascii=False, indent=2)
    OUT.write_text(
        f"// 由 work/build_data.py 自動產生，請勿手動修改\n"
        f"const rawData = {body};\n",
        encoding="utf-8",
    )
    print(f"✅ 輸出 {len(rows)} 筆 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
