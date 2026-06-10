#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 使用率データ収集
- 持ち物TOP3
- 性格TOP3
- 特性TOP3
- 技TOP6（全技種）
- 能力ポイント TOP1配分

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json
"""

import requests, json, re, time, os
from bs4 import BeautifulSoup

BASE = "https://app.gamepedia.jp/pokemon-champions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

def fetch(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "html.parser")
            print(f"  HTTP {r.status_code}")
        except Exception as e:
            print(f"  エラー({i+1}/{retries}): {e}")
            time.sleep(2)
    return None

def extract_top_n(section, label, n=3):
    """sectionからlabelのTOPn件をリストで返す"""
    h3 = None
    for tag in section.find_all(["h2","h3"]):
        if label in tag.get_text():
            h3 = tag
            break
    if not h3:
        return []
    items = []
    nxt = h3.find_next_sibling()
    while nxt and nxt.name not in ["h2","h3"]:
        a = nxt.find("a")
        if a:
            name = a.get_text(strip=True)
            if name and name not in items:
                items.append(name)
        if len(items) >= n:
            break
        nxt = nxt.find_next_sibling()
    return items

def extract_sp_top1(section):
    """
    能力ポイント TOP1配分を取得
    例: {h:2, a:32, b:0, c:0, d:0, s:32}
    """
    h3 = None
    for tag in section.find_all(["h2","h3"]):
        if "能力ポイント" in tag.get_text():
            h3 = tag
            break
    if not h3:
        return None

    # テーブルを探す
    tbl = h3.find_next("table")
    if not tbl:
        return None

    # ヘッダー行からカラム順を取得
    header_row = tbl.find("tr")
    if not header_row:
        return None
    headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th","td"])]

    # H A B C D S のカラムインデックスを特定
    stat_keys = ['h','a','b','c','d','s']
    stat_map = {}  # key -> col_index
    for key in stat_keys:
        for ci, h in enumerate(headers):
            if h == key:
                stat_map[key] = ci
                break

    if not stat_map:
        return None

    # 最初のデータ行（TOP1）を取得
    rows = tbl.find_all("tr")[1:]  # ヘッダー除外
    if not rows:
        return None

    cells = rows[0].find_all(["td","th"])
    sp = {}
    for key, ci in stat_map.items():
        if ci < len(cells):
            val = cells[ci].get_text(strip=True)
            # '·' や '-' は0扱い
            try:
                sp[key] = int(val) if val.isdigit() else 0
            except:
                sp[key] = 0
    return sp if sp else None

def parse_usage(soup, num):
    """
    ページから使用率データを全取得
    戻り値: {ポケモン名: {items, natures, abilities, moves, topSp, ...}}
    """
    result = {}

    # ポケモン名取得
    main_name = None
    h1 = soup.find("h1")
    if h1:
        main_name = re.sub(r'^#\d+\s+', '', h1.get_text(strip=True)).strip()
    if not main_name:
        return result

    # 「よく使われる技」セクション（ページ全体から取得）
    def extract_moves_global():
        """ページの「よく使われる技」リンクを全取得（TOP6）"""
        moves = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/ranking/lists/move/" in href:
                name = a.get_text(strip=True)
                # パーセント表記を除去
                name = re.sub(r'\d+\.\d+%', '', name).strip()
                if name and name not in moves:
                    moves.append(name)
            if len(moves) >= 6:
                break
        return moves

    # 「使用率」セクションを探す（ページ全体）
    # セクションタグで探す
    usage_sections = []
    for section in soup.find_all("section"):
        h2 = section.find(["h2","h3"])
        if h2 and ("使用率" in h2.get_text() or "バトルデータ" in h2.get_text()):
            if "シングル" in section.get_text() or True:
                usage_sections.append(section)

    # セクションが見つからない場合はページ全体を1セクションとして処理
    if not usage_sections:
        usage_sections = [soup]

    def parse_section(sec, name):
        data = {
            "items":    extract_top_n(sec, "持ち物", 3),
            "natures":  extract_top_n(sec, "性格",   3),
            "abilities": extract_top_n(sec, "特性",  3),
            "moves":    extract_top_n(sec, "よく使われる技", 6),
            "topSp":    extract_sp_top1(sec),
        }
        # movesが空ならページ全体から取得
        if not data["moves"]:
            data["moves"] = extract_moves_global()
        return data

    if len(usage_sections) == 1:
        data = parse_section(usage_sections[0], main_name)
        if any(data.values()):
            result[main_name] = data
        return result

    # 複数フォーム
    for sec in usage_sections:
        poke_name = main_name
        for prev in sec.find_all_previous(["h2","h3"]):
            txt = prev.get_text(strip=True)
            if "使用率" in txt or "バトルデータ" in txt:
                break
            if re.search(r'[ぁ-んァ-ヶ一-龥]', txt) and 2 <= len(txt) <= 20:
                if not any(ex in txt for ex in ["種族値","特性","技","進化","能力","タイプ"]):
                    poke_name = txt
                    break
        data = parse_section(sec, poke_name)
        if any(v for v in data.values() if v):
            result[poke_name] = data

    return result


def main():
    if not os.path.exists("poke_numbers.json"):
        print("ERROR: poke_numbers.json が見つかりません")
        return

    with open("poke_numbers.json", encoding="utf-8") as f:
        poke_numbers = json.load(f)

    print(f"対象: {len(poke_numbers)}ページ")

    result = {}
    total = len(poke_numbers)

    for idx, num in enumerate(poke_numbers):
        url = f"{BASE}/pokemon/{num}?lang=ja"
        print(f"[{idx+1}/{total}] #{num} ...", end=" ", flush=True)
        soup = fetch(url)
        if soup is None:
            print("スキップ")
            continue

        found = parse_usage(soup, num)
        if found:
            for name, data in found.items():
                result[name] = data
                moves_str = ",".join(data["moves"][:3]) if data["moves"] else "なし"
                items_str = ",".join(data["items"][:2]) if data["items"] else "なし"
                sp_str    = str(data["topSp"]) if data["topSp"] else "なし"
                print(f"{name} 技:{moves_str} 持:{items_str} SP:{sp_str}")
        else:
            print("データなし")

        time.sleep(1.0)

    with open("pokemon_usage.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ pokemon_usage.json 保存: {len(result)}体")

    for name in ["ガブリアス", "カバルドン", "ニンフィア"]:
        if name in result:
            d = result[name]
            print(f"  {name}:")
            print(f"    技: {d['moves']}")
            print(f"    持: {d['items']}")
            print(f"    特性: {d['abilities']}")
            print(f"    性格: {d['natures']}")
            print(f"    SP: {d['topSp']}")

if __name__ == "__main__":
    main()
