#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 技DB収集（タイプ・分類・威力・命中・効果）

使用方法:
  pip install requests beautifulsoup4
  python collect_move_db.py

出力:
  move_db.json → {技名: {type, cat, power, acc, effect}}

仕組み:
  各ポケモンページの「覚える技」テーブルから技情報を収集。
  同じ技が複数ページに登場しても上書きするだけなので問題なし。
"""

import requests
import json
import re
import time
from bs4 import BeautifulSoup

BASE = "https://app.gamepedia.jp/pokemon-champions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

# poke_numbers.json から読み込む（collect_pokemon_base.py が生成）
# ポケモンが追加された場合も自動対応
import os as _os
if _os.path.exists("poke_numbers.json"):
    import json as _json
    with open("poke_numbers.json", encoding="utf-8") as _f:
        POKE_NUMBERS = _json.load(_f)
    print(f"poke_numbers.json から {len(POKE_NUMBERS)} ページを読み込みました")
else:
    print("WARNING: poke_numbers.json が見つかりません")
    print("  先に collect_pokemon_base.py を実行してください")
    POKE_NUMBERS = []

def fetch(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "html.parser")
            print(f"  HTTP {r.status_code}: {url}")
        except Exception as e:
            print(f"  エラー({i+1}/{retries}): {e}")
            time.sleep(2)
    return None

def parse_move_table(soup):
    """「覚える技」テーブルから技情報を取得"""
    move_db = {}
    for table in soup.find_all("table"):
        ths = [th.get_text(strip=True) for th in table.find_all("th")]
        if "名前" not in ths or "タイプ" not in ths or "分類" not in ths:
            continue
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue
            # 技名（優先度記号 +1 -6 を除去）
            name = re.sub(r'[+\-]\d+$', '', cols[0].get_text(strip=True)).strip()
            if not name:
                continue
            move_type = cols[1].get_text(strip=True)
            cat       = cols[2].get_text(strip=True)
            power_raw = cols[3].get_text(strip=True)
            acc_raw   = cols[4].get_text(strip=True)
            effect    = cols[6].get_text(strip=True) if len(cols) > 6 else ""
            power = int(power_raw) if power_raw.isdigit() else 0
            acc   = acc_raw.replace("%", "") if acc_raw not in ("—", "") else "—"
            move_db[name] = {
                "type"  : move_type,
                "cat"   : cat,
                "power" : power,
                "acc"   : acc,
                "effect": effect[:100]
            }
    return move_db

def main():
    result = {}
    total = len(POKE_NUMBERS)

    for idx, num in enumerate(POKE_NUMBERS):
        url = f"{BASE}/pokemon/{num}?lang=ja"
        print(f"[{idx+1}/{total}] #{num} ...", end=" ", flush=True)
        soup = fetch(url)
        if soup is None:
            print("スキップ")
            continue

        found = parse_move_table(soup)
        print(f"{len(found)}技")
        result.update(found)
        time.sleep(1.5)

    with open("move_db.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✓ move_db.json 保存: {len(result)}技")

if __name__ == "__main__":
    main()
