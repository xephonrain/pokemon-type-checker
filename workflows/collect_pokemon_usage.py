#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 持ち物・性格使用率TOP3を収集

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json → {
    "ガブリアス": {
      "items":   ["こだわりスカーフ", "きあいのタスキ", "とつげきチョッキ"],
      "natures": ["ようき", "いじっぱり", "おくびょう"]
    }, ...
  }

前提:
  collect_pokemon_base.py を先に実行して poke_numbers.json を生成しておく
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

def parse_usage(soup):
    """
    ページから持ち物TOP3・性格TOP3を取得
    戻り値: {フォーム名_or_メイン名: {items:[...], natures:[...]}}
    """
    result = {}

    # h1からメインポケモン名を取得
    main_name = None
    h1 = soup.find("h1")
    if h1:
        main_name = re.sub(r'^#\d+\s+', '', h1.get_text(strip=True)).strip()
    if not main_name:
        return result

    # 「使用率データ...シングル」セクションを全取得
    usage_sections = []
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if h2 and "使用率データ" in h2.get_text() and "シングル" in h2.get_text():
            usage_sections.append(section)

    if not usage_sections:
        return result

    def extract_top3(section, label):
        """sectionからlabel(例:'持ち物')のTOP3を取得"""
        h3 = section.find("h3", string=label)
        if not h3:
            # 部分一致で探す
            for tag in section.find_all("h3"):
                if label in tag.get_text():
                    h3 = tag
                    break
        if not h3:
            return []
        items = []
        nxt = h3.find_next_sibling()
        while nxt and nxt.name != "h3":
            a = nxt.find("a")
            if a:
                name = a.get_text(strip=True)
                if name and name not in items:
                    items.append(name)
            if len(items) >= 3:
                break
            nxt = nxt.find_next_sibling()
        return items

    # セクションが1つの場合
    if len(usage_sections) == 1:
        sec = usage_sections[0]
        result[main_name] = {
            "items":   extract_top3(sec, "持ち物"),
            "natures": extract_top3(sec, "性格"),
        }
        return result

    # 複数フォームの場合
    for sec in usage_sections:
        # セクション直前のh2/h3からポケモン名を推定
        poke_name = main_name
        for prev in sec.find_all_previous(["h2", "h3"]):
            txt = prev.get_text(strip=True)
            if "使用率データ" in txt:
                break
            if re.search(r'[ぁ-んァ-ヶ一-龥]', txt) and 2 <= len(txt) <= 20:
                if not any(ex in txt for ex in ["種族値","特性","覚える技","進化","能力"]):
                    poke_name = txt
                    break
        result[poke_name] = {
            "items":   extract_top3(sec, "持ち物"),
            "natures": extract_top3(sec, "性格"),
        }

    return result


def main():
    # poke_numbers.json から番号リストを読み込む
    if not os.path.exists("poke_numbers.json"):
        print("ERROR: poke_numbers.json が見つかりません")
        print("先に collect_pokemon_base.py を実行してください")
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

        found = parse_usage(soup)
        if found:
            for name, data in found.items():
                result[name] = data
                items_str   = ",".join(data["items"][:2])   if data["items"]   else "なし"
                natures_str = ",".join(data["natures"][:2]) if data["natures"] else "なし"
                print(f"{name} 持:{items_str} 性:{natures_str}")
        else:
            print("データなし")

        time.sleep(1.0)

    with open("pokemon_usage.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ pokemon_usage.json 保存: {len(result)}体")

    # サンプル表示
    for name in ["ガブリアス", "ニンフィア", "カバルドン"]:
        if name in result:
            d = result[name]
            print(f"  {name}: 持={d['items']} 性={d['natures']}")

if __name__ == "__main__":
    main()
