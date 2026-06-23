#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 使用率データ収集
取得元: https://champs.pokedb.tokyo
方式: requests + BeautifulSoup（playwright不要）

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json
"""

import requests, json, re, time
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
    """ランキングページから全ポケモンのIDと名前を取得"""
    print("ポケモン一覧取得中...")
    pokemons = []
    seen_ids = set()
    page = 1

    while True:
        url = f"{BASE}/pokemon/list?rule=0&page={page}"
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

    lines = [l.strip() for l in soup.get_text(separator='\n').split('\n') if l.strip()]

    sections = {'技': 'moves', '特性': 'abilities', '能力補正': 'natures', '持ち物': 'items'}
    limits   = {'moves': 10, 'abilities': 3, 'natures': 3, 'items': 5}
    current  = None

    for line in lines:
        if line in sections:
            current = sections[line]
            continue
        if line == '能力ポイント':
            current = 'sp'
            continue

        if current and current != 'sp':
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m:
                name = m.group(1).strip()
                if name and not re.match(r'^\d+$', name):
                    lst = result[current]
                    if len(lst) < limits[current] and name not in lst:
                        lst.append(name)
        elif current == 'sp':
            if re.search(r'[HABCDShabcds]\s+\d+', line):
                sp = {"h":0,"a":0,"b":0,"c":0,"d":0,"s":0}
                for k, v in re.findall(r'([HABCDShabcds])\s+(\d+)', line):
                    sp[k.lower()] = int(v)
                if 1 <= sum(sp.values()) <= 128:
                    result['topSp'] = sp
                    current = None

    return result

def main():
    print("=== champs.pokedb.tokyo から使用率データ取得 ===\n")

    pokemons = get_poke_list()
    if not pokemons:
        print("ERROR: ポケモン一覧が取得できません")
        return

    result = {}
    total = len(pokemons)

    for idx, poke in enumerate(pokemons):
        pid  = poke['id']
        name = poke['name']
        url  = f"{BASE}/pokemon/show/{pid}?rule=0"
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

    for name in ["ガブリアス", "ミミッキュ", "アーマーガア"]:
        if name in result:
            d = result[name]
            print(f"  {name}: 技{d['moves'][:3]} 持{d['items'][:2]} SP:{d['topSp']}")

if __name__ == "__main__":
    main()
