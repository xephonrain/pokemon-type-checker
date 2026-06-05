#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 各ポケモンの技TOP6を収集

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_moves.py

出力:
  pokemon_moves.json → {ポケモン名: ["技1", "技2", ...最大6個]}
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

def parse_page(soup):
    """
    ページから {ポケモン名: [技名TOP6]} を取得。

    構造:
      <section class="section core-only">
        <h2 class="section-title">使用率データ <span>シーズンXX シングル</span></h2>
        <div class="usage-grid">
          <div class="usage-col">
            <h3>技</h3>
            <div class="pct-row"><a>技名</a> 85.2%</div>
            ...
          </div>
        </div>
      </section>

    フォームが複数ある場合、「使用率データ...シングル」セクションが複数存在する。
    それぞれのセクションに対応するポケモン名は、セクション直前の
    「pokemon-name」クラスや「form-title」クラスのタグから取得する。
    見つからない場合はh1のメイン名を使用する。
    """
    result = {}

    # h1からメインポケモン名を取得:「#003 フシギバナ」→「フシギバナ」
    main_name = None
    h1 = soup.find("h1")
    if h1:
        main_name = re.sub(r'^#\d+\s+', '', h1.get_text(strip=True)).strip()

    if not main_name:
        return result

    # 全「使用率データ...シングル」セクションを取得
    usage_sections = []
    for section in soup.find_all("section"):
        h2 = section.find("h2")
        if not h2:
            continue
        h2_txt = h2.get_text(strip=True)
        if "使用率データ" in h2_txt and "シングル" in h2_txt:
            usage_sections.append(section)

    if not usage_sections:
        return result

    # セクションが1つ → メイン名を使う
    if len(usage_sections) == 1:
        moves = _extract_moves(usage_sections[0])
        if moves:
            result[main_name] = moves
        return result

    # セクションが複数（フォームあり）
    # 各セクションの直前にあるポケモン名らしいテキストを探す
    for section in usage_sections:
        # セクションの直前の兄弟・親を遡ってフォーム名を探す
        poke_name = main_name  # デフォルトはメイン名

        # セクションの直前のh2/h3/div等からポケモン名を推定
        # 「使用率データ」以外で日本語名を含むh2を探す
        for prev_tag in section.find_all_previous(["h2", "h3"]):
            txt = prev_tag.get_text(strip=True)
            # 除外ワードを含まない日本語テキストならポケモン名候補
            if _is_valid_poke_name(txt):
                poke_name = txt
                break
            # 「使用率データ」h2に到達したら探索終了（別セクション）
            if "使用率データ" in txt:
                break

        moves = _extract_moves(section)
        if moves:
            result[poke_name] = moves

    return result

def _extract_moves(section):
    """sectionから技TOP6を取得"""
    h3_waza = section.find("h3", string="技")
    if not h3_waza:
        return []
    moves = []
    nxt = h3_waza.find_next_sibling()
    while nxt:
        if nxt.name == "h3":
            break
        a = nxt.find("a")
        if a:
            name = a.get_text(strip=True)
            if name and name not in moves:
                moves.append(name)
        if len(moves) >= 6:
            break
        nxt = nxt.find_next_sibling()
    return moves

def _is_valid_poke_name(txt):
    """ポケモン名として有効かチェック"""
    EXCLUDE = [
        "種族値", "覚える技", "特性", "進化系統", "使用率",
        "メガシンカ", "フォルムチェンジ", "関連する", "登場バージョン",
        "能力ポイント", "持ち物", "性格", "物理", "特殊", "変化",
        "採用ポケモン", "覚えるポケモン", "シーズン", "ランキング",
    ]
    for ex in EXCLUDE:
        if ex in txt:
            return False
    # 英数字のみは除外
    if re.match(r'^[a-zA-Z0-9\s\-#]+$', txt):
        return False
    # 日本語を含み適切な長さ
    return bool(re.search(r'[ぁ-んァ-ヶ一-龥]', txt)) and 2 <= len(txt) <= 20

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

        found = parse_page(soup)
        names = list(found.keys())
        print(f"{', '.join(names) if names else '（技データなし）'}")
        result.update(found)
        time.sleep(1.5)

    with open("pokemon_moves.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✓ pokemon_moves.json 保存: {len(result)}体")

if __name__ == "__main__":
    main()
