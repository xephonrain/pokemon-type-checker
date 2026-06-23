#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 使用率データ収集
取得元: https://champs.pokedb.tokyo

取得データ:
  - 技TOP10（使用率%付き）
  - 特性TOP3
  - 性格TOP3
  - 持ち物TOP5
  - 能力ポイント TOP1配分（個別）

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json
"""

import requests, json, re, time, os
from bs4 import BeautifulSoup

BASE = "https://champs.pokedb.tokyo"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
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

def get_poke_list():
    """ポケモンランキングページから全ポケモンのIDと名前を取得"""
    print("ポケモン一覧取得中...")
    pokemons = []
    page = 1
    seen_ids = set()

    while True:
        url = f"{BASE}/pokemon/list?rule=0&page={page}"
        soup = fetch(url)
        if not soup:
            break

        # ポケモンリンクを取得
        links = soup.select('a[href*="/pokemon/show/"]')
        if not links:
            break

        new_found = False
        for a in links:
            href = a.get('href', '')
            m = re.search(r'/pokemon/show/([0-9]+-[0-9]+)', href)
            if not m:
                continue
            pid = m.group(1)
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            name = a.get_text(strip=True)
            # 数字・記号のみは除外
            if name and not re.match(r'^[\d\s]+$', name):
                pokemons.append({'id': pid, 'name': name})
                new_found = True

        if not new_found:
            break
        page += 1
        time.sleep(0.5)

    print(f"  {len(pokemons)}体取得")
    return pokemons

def parse_sp(text):
    """
    能力ポイントテキストをパース
    例: "H 2 A 32 S 32" -> {"h":2,"a":32,"b":0,"c":0,"d":0,"s":32}
    """
    sp = {"h":0,"a":0,"b":0,"c":0,"d":0,"s":0}
    pairs = re.findall(r'([HABCDShabcds])\s+(\d+)', text)
    for k, v in pairs:
        sp[k.lower()] = int(v)
    return sp

def parse_pokemon(soup, pid, name):
    """個別ページから使用率データを取得"""
    result = {
        'moves':     [],
        'abilities': [],
        'natures':   [],
        'items':     [],
        'topSp':     None,
    }

    text = soup.get_text(separator='\n')
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # ---- 技 ----
    # 「技」セクションを探す: "じしん 99.7%" のパターン
    in_moves = False
    for i, line in enumerate(lines):
        if line == '技':
            in_moves = True
            continue
        if in_moves:
            if line in ['特性', '能力補正', '持ち物', '能力ポイント']:
                break
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m:
                result['moves'].append(m.group(1))
                if len(result['moves']) >= 10:
                    break

    # ---- 特性 ----
    in_ab = False
    for line in lines:
        if line == '特性':
            in_ab = True
            continue
        if in_ab:
            if line in ['能力補正', '持ち物', '能力ポイント', '技']:
                break
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m and not re.match(r'^\d+$', m.group(1)):
                result['abilities'].append(m.group(1))
                if len(result['abilities']) >= 3:
                    break

    # ---- 性格 ----
    in_nat = False
    for line in lines:
        if line == '能力補正':
            in_nat = True
            continue
        if in_nat:
            if line in ['持ち物', '能力ポイント', '技', '特性']:
                break
            m = re.match(r'^([ぁ-ん]+)\s*\(.*?\)\s+([\d.]+)%$', line)
            if m:
                result['natures'].append(m.group(1))
                if len(result['natures']) >= 3:
                    break

    # ---- 持ち物 ----
    in_item = False
    for line in lines:
        if line == '持ち物':
            in_item = True
            continue
        if in_item:
            if line in ['能力ポイント', '技', '特性', '能力補正']:
                break
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m and not re.match(r'^\d+$', m.group(1)):
                result['items'].append(m.group(1))
                if len(result['items']) >= 5:
                    break

    # ---- 能力ポイント（個別TOP1） ----
    # "H 2 A 32 S 32" のようなパターンを探す
    sp_pattern = re.compile(r'^([HABCDShabcds]\s+\d+\s*)+$')
    in_sp = False
    for line in lines:
        if '能力ポイント' in line:
            in_sp = True
            continue
        if in_sp:
            # "H 2 A 32 S 32" 形式の行
            if re.search(r'[HABCDShabcds]\s+\d+', line):
                sp = parse_sp(line)
                total = sum(sp.values())
                if 1 <= total <= 128:  # 妥当な範囲
                    result['topSp'] = sp
                    break

    return result

def main():
    print("=== champs.pokedb.tokyo から使用率データ取得 ===\n")

    # ポケモン一覧取得
    pokemons = get_poke_list()
    if not pokemons:
        print("ERROR: ポケモン一覧が取得できません")
        return

    result = {}
    total = len(pokemons)

    for idx, poke in enumerate(pokemons):
        pid = poke['id']
        name = poke['name']
        url = f"{BASE}/pokemon/show/{pid}?rule=0"
        print(f"[{idx+1}/{total}] {name} ({pid}) ...", end=" ", flush=True)

        soup = fetch(url)
        if soup is None:
            print("スキップ")
            continue

        data = parse_pokemon(soup, pid, name)
        result[name] = data

        # サマリー表示
        moves_str = ",".join(data['moves'][:3]) if data['moves'] else "なし"
        items_str = ",".join(data['items'][:2]) if data['items'] else "なし"
        sp_str    = str(data['topSp']) if data['topSp'] else "なし"
        print(f"技:{moves_str} 持:{items_str} SP:{sp_str}")

        time.sleep(1.0)

    with open("pokemon_usage.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ pokemon_usage.json 保存: {len(result)}体")

    # 検証サンプル
    for name in ["ガブリアス", "ミミッキュ", "アーマーガア"]:
        if name in result:
            d = result[name]
            print(f"\n  {name}:")
            print(f"    技:   {d['moves'][:6]}")
            print(f"    持物: {d['items'][:3]}")
            print(f"    特性: {d['abilities']}")
            print(f"    性格: {d['natures']}")
            print(f"    SP:   {d['topSp']}")

if __name__ == "__main__":
    main()
