# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""臺北市街頭藝人資料 ETL。

輸入（原始檔，不修改）：
- data/taipei_street_artist_stats.csv   臺北市政府主計處｜臺北市藝文館所及街頭藝人（年資料）
- data/taipei_street_artist_venues.csv  臺北市政府文化局｜臺北市街頭藝人展演場地資訊（場地名冊）

輸出：
- work/clean_street_art.csv  每年一列：有效證照數、表演場地數與標準化指標
- work/clean_venues.csv      每個場地一列：標準化後的開放表演類別
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_STATS = ROOT / "data" / "taipei_street_artist_stats.csv"
RAW_VENUES = ROOT / "data" / "taipei_street_artist_venues.csv"
OUT_YEARLY = ROOT / "work" / "clean_street_art.csv"
OUT_VENUES = ROOT / "work" / "clean_venues.csv"

COL_LICENCES = "街頭藝人/許可證有效證照數[張]"
COL_VENUES = "街頭藝人/表演場地數[處]"
BASE_YEAR = 102  # 第一個有街頭藝人資料的年度，作為指數基期

TYPES = ["表演藝術類", "視覺藝術類", "工藝藝術類"]
# 開放組合（互斥），圓餅圖用；順序固定
COMBOS = {
    (True, True, True): "三類皆可",
    (True, True, False): "表演＋視覺",
    (True, False, False): "僅表演藝術",
    (False, True, True): "視覺＋工藝",
}
# 出現這些字眼代表該場地對表演內容另有限制
RESTRICT_WORDS = ["限", "僅", "除外", "不得", "為主", "之歌唱", "音樂性"]
# 主管機關名稱不一致的統一
AGENCY_ALIASES = {
    "市場處": "臺北市市場處",
    "工務局衛生下水道工程處": "臺北市政府工務局衛生下水道工程處",
}

errors: list[str] = []
warnings: list[str] = []


def clean_text(s: str) -> str:
    """把儲存格內的換行與多餘空白收成單一空格。"""
    return re.sub(r"\s+", " ", s).strip()


def to_int(s: str, where: str) -> int:
    try:
        return int(s.replace(",", "").strip())
    except ValueError:
        errors.append(f"{where}：無法轉成整數「{s}」")
        return 0


# ---------- 年資料 ----------

def etl_yearly() -> list[dict]:
    with RAW_STATS.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for col in ("統計期", COL_LICENCES, COL_VENUES):
        if col not in rows[0]:
            sys.exit(f"年資料缺少欄位：{col}")

    out = []
    for r in rows:
        m = re.fullmatch(r"(\d+)年", r["統計期"].strip())
        if not m:
            errors.append(f"統計期格式不對：{r['統計期']}")
            continue
        year = int(m.group(1))
        lic = to_int(r[COL_LICENCES], f"{year}年 證照數")
        ven = to_int(r[COL_VENUES], f"{year}年 場地數")
        if year < BASE_YEAR:
            # 102 年以前尚未統計，原始檔填 0；確認真的是 0 後視為「無資料」排除
            if lic or ven:
                errors.append(f"{year}年 預期為無資料(0)，實際為 {lic}/{ven}")
            continue
        if lic <= 0 or ven <= 0:
            errors.append(f"{year}年 證照數或場地數不是正數：{lic}/{ven}")
        out.append({"year": year, "licences": lic, "venues": ven})

    years = [r["year"] for r in out]
    if years != list(range(BASE_YEAR, years[-1] + 1)):
        errors.append(f"年度不連續：{years}")

    base = out[0]["licences"]
    prev = None
    for r in out:
        # 標準化指標
        r["licences_per_venue"] = round(r["licences"] / r["venues"], 2)
        r["licences_index"] = round(r["licences"] / base * 100, 1)
        r["licences_yoy_pct"] = (
            round((r["licences"] - prev["licences"]) / prev["licences"] * 100, 1) if prev else ""
        )
        r["venues_yoy_pct"] = (
            round((r["venues"] - prev["venues"]) / prev["venues"] * 100, 1) if prev else ""
        )
        # 單年變動超過 ±100% 視為統計口徑可能改變，標記出來
        r["flag"] = "單年變動超過100%，統計口徑可能改變" if (
            r["licences_yoy_pct"] != "" and abs(r["licences_yoy_pct"]) > 100) else ""
        prev = r
    return out


# ---------- 場地名冊 ----------

def classify(raw: str) -> tuple[bool, bool, bool]:
    t = raw.replace(" ", "")
    perform = any(k in t for k in ("表演", "音樂"))
    visual = "視覺" in t
    craft = "工藝" in t
    return perform, visual, craft


def etl_venues() -> list[dict]:
    with RAW_VENUES.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    out = []
    seen_ids = set()
    for i, r in enumerate(rows, start=1):
        name = clean_text(r["展演地"])
        agency = clean_text(r["主管機關"])
        # 同一格內的多個機關以換行分隔；第一個為主管機關
        agency_main = AGENCY_ALIASES.get(agency.split(" ")[0], agency.split(" ")[0])
        raw_types = clean_text(r["開放表演類型"])
        perform, visual, craft = classify(raw_types)

        vid = r["項次"].strip()
        if not vid:
            # 原始檔有一列項次空白（前一個場地的其他點位），補上流水號
            vid = f"{int(out[-1]['venue_id'].split('-')[0])}-2" if out else str(i)
            warnings.append(f"第 {i} 列項次空白（{name}），補為 {vid}")
        if vid in seen_ids:
            errors.append(f"項次重複：{vid}")
        seen_ids.add(vid)

        if not name:
            errors.append(f"第 {i} 列沒有展演地名稱")
        combo = COMBOS.get((perform, visual, craft))
        if combo is None:
            errors.append(f"{name}：無法歸類的開放表演類型「{raw_types}」")
            continue

        out.append({
            "venue_id": vid,
            "venue": name,
            "agency": agency_main,
            "types_raw": raw_types,
            "perform": int(perform),
            "visual": int(visual),
            "craft": int(craft),
            "combo": combo,
            "restricted": int(any(w in raw_types for w in RESTRICT_WORDS)),
        })

    # 驗證：各開放組合加總 = 場地總數（互斥分類）
    combo_total = sum(sum(1 for v in out if v["combo"] == c) for c in COMBOS.values())
    if combo_total != len(rows):
        errors.append(f"開放組合加總 {combo_total} ≠ 原始場地數 {len(rows)}")
    # 驗證：每個場地至少開放一種類別
    for v in out:
        if v["perform"] + v["visual"] + v["craft"] == 0:
            errors.append(f"{v['venue']} 沒有任何開放類別")
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 主控台預設不是 UTF-8
    yearly = etl_yearly()
    venues = etl_venues()

    # 交叉核對：場地名冊筆數 vs. 最新年度統計的場地數（時點不同，只提醒不報錯）
    latest = yearly[-1]
    if abs(latest["venues"] - len(venues)) > 5:
        warnings.append(f"場地名冊 {len(venues)} 處與 {latest['year']} 年統計 {latest['venues']} 處差距超過 5")

    if errors:
        sys.exit("❌ 驗證失敗：\n" + "\n".join(errors))

    write_csv(OUT_YEARLY, yearly)
    write_csv(OUT_VENUES, venues)

    for w in warnings:
        print("⚠️ " + w)
    print(f"✅ 年資料 {len(yearly)} 列（{yearly[0]['year']}–{latest['year']} 年）→ {OUT_YEARLY.relative_to(ROOT)}")
    print(f"✅ 場地名冊 {len(venues)} 處 → {OUT_VENUES.relative_to(ROOT)}")
    for c in COMBOS.values():
        print(f"   {c}：{sum(1 for v in venues if v['combo'] == c)} 處")
    for t, k in zip(TYPES, ("perform", "visual", "craft")):
        n = sum(v[k] for v in venues)
        print(f"   可進行{t}：{n} 處（{n / len(venues):.1%}）")
    print(f"   名冊 {len(venues)} 處，{latest['year']} 年統計 {latest['venues']} 處")


if __name__ == "__main__":
    main()
