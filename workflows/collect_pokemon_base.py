#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 全ポケモン基本データ収集
一覧ページのテーブルから全種族値を一括取得する

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_base.py

出力:
  pokemon_base.json  → 種族値・タイプ・特性
  poke_numbers.json  → 個別ページ番号リスト（技収集に使用）
"""

import requests, json, re, time
from bs4 import BeautifulSoup

BASE = "https://app.gamepedia.jp/pokemon-champions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

ALL_TYPES = [
    "かくとう","フェアリー","ドラゴン","ゴースト","エスパー",
    "ノーマル","ほのお","みず","くさ","でんき","こおり",
    "どく","じめん","ひこう","むし","いわ","あく","はがね",
]

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

def split_types(type_str):
    s = type_str.strip().replace(" ", "")
    if not s: return "", ""
    for t in ALL_TYPES:
        if s.startswith(t):
            rest = s[len(t):]
            return t, rest if rest in ALL_TYPES else ""
    return s, ""

def clean_name(name):
    name = re.sub(r'([A-Z])M$', r'\1', name)
    name = re.sub(r'(?<=[^\x00-\x7F])M$', '', name)
    return name.strip()

def main():
    # ============================================================
    # Step1: 一覧ページからテーブルを直接パース（種族値・タイプ一括取得）
    # ============================================================
    url = f"{BASE}/pokemon?lang=ja"
    print(f"[Step1] 一覧ページ取得: {url}")
    soup = fetch(url)
    if not soup:
        print("ERROR: 一覧ページ取得失敗")
        return

    # 一覧テーブルを探す（HP/こうげき/ぼうぎょ...の列がある）
    list_table = None
    for tbl in soup.find_all('table'):
        ths = [th.get_text(strip=True) for th in tbl.find_all('th')]
        if 'HP' in ths and 'こうげき' in ths and 'ぼうぎょ' in ths:
            list_table = tbl
            break

    if not list_table:
        print("ERROR: 種族値テーブルが見つかりません")
        return

    headers = [th.get_text(strip=True) for th in list_table.find_all('th')]
    col = {h: i for i, h in enumerate(headers)}

    merged = []
    poke_numbers = []
    num_to_names = {}

    rows = list_table.find_all('tr')[1:]
    print(f"  → {len(rows)}行を検出")

    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 8: continue

        # 名前・リンク
        name_cell = cols[1] if len(cols) > 1 else cols[0]
        a = name_cell.find('a')
        if not a: continue
        href = a.get('href', '')
        m = re.search(r'/pokemon/(\d+)', href)
        if not m: continue
        num = int(m.group(1))

        name = clean_name(a.get_text(strip=True))
        if not name: continue

        # タイプ
        type_cell = cols[col.get('タイプ', 2)] if 'タイプ' in col else cols[2]
        t1, t2 = split_types(type_cell.get_text(strip=True))

        # 種族値
        def gv(key, fallback_idx):
            idx = col.get(key, fallback_idx)
            if idx < len(cols):
                try: return int(cols[idx].get_text(strip=True))
                except: return 0
            return 0

        entry = {
            'name': name,
            'hp':   gv('HP',        col.get('HP', 3)),
            'atk':  gv('こうげき',    col.get('こうげき', 4)),
            'def':  gv('ぼうぎょ',    col.get('ぼうぎょ', 5)),
            'spa':  gv('とくこう',    col.get('とくこう', 6)),
            'spd':  gv('とくぼう',    col.get('とくぼう', 7)),
            'spe':  gv('すばやさ',    col.get('すばやさ', 8)),
            't1':  t1,
            't2':  t2,
            'abilities': [],
        }
        merged.append(entry)

        if num not in poke_numbers:
            poke_numbers.append(num)
        num_to_names.setdefault(num, []).append(name)

    print(f"  → {len(merged)}体を一覧テーブルから取得")

    # ============================================================
    # Step2: 個別ページから特性を取得
    # ============================================================
    print(f"\n[Step2] 特性を個別ページから取得 ({len(poke_numbers)}ページ)")

    ability_map = {}  # {ポケモン名: [特性リスト]}
    total = len(poke_numbers)

    for idx, num in enumerate(sorted(poke_numbers)):
        url2 = f"{BASE}/pokemon/{num}?lang=ja"
        names_on_page = num_to_names.get(num, [])
        print(f"  [{idx+1}/{total}] #{num} {','.join(names_on_page[:2])} ...", end=" ", flush=True)

        soup2 = fetch(url2)
        if not soup2:
            print("スキップ")
            continue

        # 特性の取得
        abilities = []

        # パターン1: ca-ability クラス
        for div in soup2.find_all('div', class_='ca-ability'):
            name_div = div.find('div', class_='ca-ability-name')
            if not name_div: continue
            a = name_div.find('a')
            ab = a.get_text(strip=True) if a else name_div.get_text(strip=True)
            if ab and ab not in abilities:
                abilities.append(ab)

        # パターン2: テーブルのth「特性」行
        if not abilities:
            for tag in soup2.find_all(['td', 'dd']):
                prev = tag.find_previous(['th', 'dt'])
                if prev and '特性' in prev.get_text():
                    for part in re.split(r'[/／・\n,、]', tag.get_text(strip=True)):
                        ab = part.strip()
                        if ab and 2 <= len(ab) <= 15 and ab not in abilities:
                            abilities.append(ab)

        print(f"特性: {abilities[:3]}")

        for name in names_on_page:
            ability_map[name] = abilities

        time.sleep(1.0)

    # ============================================================
    # Step3: 特性をマージして保存
    # ============================================================
    for entry in merged:
        entry['abilities'] = ability_map.get(entry['name'], [])

    with open('pokemon_base.json', 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    with open('poke_numbers.json', 'w', encoding='utf-8') as f:
        json.dump(sorted(poke_numbers), f, ensure_ascii=False)

    # 取得確認
    zero = [p for p in merged if p['hp'] == 0 and p['atk'] == 0]
    print(f"\n✓ pokemon_base.json: {len(merged)}体")
    print(f"✓ poke_numbers.json: {len(poke_numbers)}ページ")
    if zero:
        print(f"⚠ 種族値未取得: {len(zero)}体 → {[p['name'] for p in zero[:5]]}")

    print("\nサンプル:")
    for name in ['アーボック', 'カバルドン', 'ニンフィア', 'ガブリアス']:
        p = next((x for x in merged if x['name'] == name), None)
        if p:
            print(f"  {p['name']}: HP{p['hp']} A{p['atk']} B{p['def']} C{p['spa']} D{p['spd']} S{p['spe']}  t1={p['t1']} t2={p['t2']}")

if __name__ == "__main__":
    main()
