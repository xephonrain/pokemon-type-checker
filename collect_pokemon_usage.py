#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 使用率データ収集
取得元: https://champs.pokedb.tokyo
方式: requests + BeautifulSoup

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json
"""

import requests, json, re, time
from bs4 import BeautifulSoup

BASE   = "https://champs.pokedb.tokyo"
SEASON = 3   # 現在のシーズン番号（毎シーズン更新）

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
    """ランキングページから全ポケモンのIDと名前を取得"""
    print("ポケモン一覧取得中...")
    pokemons = []
    seen_ids = set()
    page = 1

    while True:
        url = f"{BASE}/pokemon/list?season={SEASON}&rule=0&page={page}"
        soup = fetch(url)
        if not soup:
            break

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
            name = re.sub(r'^\d+\s*', '', name).strip()
            if name and not re.match(r'^[\d\s]+$', name):
                pokemons.append({'id': pid, 'name': name})
                new_found = True

        if not new_found:
            break
        page += 1
        time.sleep(0.5)

    print(f"  {len(pokemons)}体取得")
    return pokemons

def parse_pokemon(soup):
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

    current = None
    sp_mode = False

    for line in lines:
        # セクション検出
        if line == '技':
            current = 'moves'
            sp_mode = False
            continue
        elif line == '特性':
            current = 'abilities'
            sp_mode = False
            continue
        elif line in ('能力補正', '性格'):
            current = 'natures'
            sp_mode = False
            continue
        elif line == '持ち物':
            current = 'items'
            sp_mode = False
            continue
        elif line == '能力ポイント':
            current = 'sp'
            sp_mode = True
            continue

        # セクション外はスキップ
        if current is None:
            continue

        # 技・持ち物: "名前 XX.X%" パターン
        if current in ('moves', 'items'):
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m:
                name = m.group(1).strip()
                if name and not re.match(r'^\d+$', name):
                    lst = result[current]
                    limit = 10 if current == 'moves' else 5
                    if len(lst) < limit and name not in lst:
                        lst.append(name)
            continue

        # 特性: "名前 XX.X%" or 番号行をスキップ
        if current == 'abilities':
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m:
                name = m.group(1).strip()
                if name and not re.match(r'^\d+$', name) and '↑' not in name and '↓' not in name:
                    if len(result['abilities']) < 3 and name not in result['abilities']:
                        result['abilities'].append(name)
            continue

        # 性格: "ようき (S↑C↓) XX.X%" パターン
        if current == 'natures':
            # "ようき (S↑C↓) 60.4%" 形式
            m = re.match(r'^([ぁ-ん]+)\s*[\(（].*?[\)）]?\s*([\d.]+)%', line)
            if not m:
                # "ようき 60.4%" シンプル形式
                m = re.match(r'^([ぁ-ん]+)\s+([\d.]+)%', line)
            if m:
                name = m.group(1).strip()
                if len(result['natures']) < 3 and name not in result['natures']:
                    result['natures'].append(name)
            continue

        # 能力ポイント: H/A/B/C/D/S + 数値
        if current == 'sp':
            if re.search(r'[HABCDShabcds]\s*\d+', line):
                sp = {"h":0,"a":0,"b":0,"c":0,"d":0,"s":0}
                for k, v in re.findall(r'([HABCDShabcds])\s*(\d+)', line):
                    sp[k.lower()] = int(v)
                total = sum(sp.values())
                if 1 <= total <= 128:
                    result['topSp'] = sp
                    current = None
            continue

    return result

def get_latest_season():
    """最新シーズン番号を自動取得"""
    soup = fetch(f"{BASE}/pokemon/list?rule=0")
    if not soup:
        return SEASON
    # season=X のリンクから最大値を取得
    seasons = re.findall(r'season=(\d+)', soup.get_text())
    if seasons:
        return max(int(s) for s in seasons)
    return SEASON

def main():
    print("=== champs.pokedb.tokyo から使用率データ取得 ===\n")

    # 最新シーズンを自動検出
    season = get_latest_season()
    print(f"シーズン: M-{season}\n")

    pokemons = get_poke_list()
    if not pokemons:
        print("ERROR: ポケモン一覧が取得できません")
        return

    result = {}
    total = len(pokemons)

    for idx, poke in enumerate(pokemons):
        pid  = poke['id']
        name = poke['name']
        url  = f"{BASE}/pokemon/show/{pid}?season={season}&rule=0"
        print(f"[{idx+1}/{total}] {name} ({pid}) ...", end=" ", flush=True)

        soup = fetch(url)
        if soup is None:
            print("スキップ")
            continue

        data = parse_pokemon(soup)
        result[name] = data

        moves_str = ",".join(data['moves'][:3]) if data['moves'] else "なし"
        items_str = ",".join(data['items'][:2]) if data['items'] else "なし"
        sp_str    = str(data['topSp']) if data['topSp'] else "なし"
        print(f"技:{moves_str} 持:{items_str} SP:{sp_str}")

        time.sleep(1.0)

    with open("pokemon_usage.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {len(result)}体 → pokemon_usage.json")

    for check_name in ["ガブリアス", "ミミッキュ", "アーマーガア"]:
        if check_name in result:
            d = result[check_name]
            print(f"\n  {check_name}:")
            print(f"    技:   {d['moves'][:5]}")
            print(f"    持物: {d['items'][:3]}")
            print(f"    特性: {d['abilities']}")
            print(f"    性格: {d['natures']}")
            print(f"    SP:   {d['topSp']}")

if __name__ == "__main__":
    main()
