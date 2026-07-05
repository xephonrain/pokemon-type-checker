#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 使用率データ収集
取得元: https://champs.pokedb.tokyo
方式: requests + BeautifulSoup

HTML構造（get_text後の行パターン）:
  技:       名前 / 数値 / %
  特性:     連番 / 名前 / %表記 / %表記（重複）
  能力補正: 連番 / 名前 / ( / 上昇 / 下降 / ) / %表記 / %表記
  持ち物:   連番 / 名前 / %表記 / %表記
  能力ポイント: 合算セクション→スキップ、個別セクション→
                連番 / 略称(AS等) / %表記 / (H 数値)? / A 数値 / (B 数値)? / (C 数値)? / (D 数値)? / (S 数値)?

使用方法:
  pip install requests beautifulsoup4
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json
"""

import requests, json, re, time

BASE   = "https://champs.pokedb.tokyo"
SEASON = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
}

def fetch_html(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return r.text
            print(f"  HTTP {r.status_code}")
        except Exception as e:
            print(f"  エラー({i+1}/{retries}): {e}")
            time.sleep(2)
    return None

def get_lines(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    return [l.strip() for l in soup.get_text(separator='\n').split('\n') if l.strip()]

def get_poke_list():
    """ランキングページから全ポケモンのIDと名前を取得"""
    print("ポケモン一覧取得中...")
    pokemons = []
    seen_ids = set()
    page = 1

    while True:
        url = f"{BASE}/pokemon/list?season={SEASON}&rule=0&page={page}"
        html = fetch_html(url)
        if not html:
            break
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

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

def is_pct(s):
    """'99.4%' や '99.4' のような文字列か判定"""
    return bool(re.match(r'^[\d.]+%?$', s))

def parse_pokemon(lines):
    """個別ページから使用率データを取得（行単位パーサー）"""
    result = {
        'moves':     [],
        'abilities': [],
        'natures':   [],
        'items':     [],
        'topSp':     None,
    }

    n = len(lines)
    i = 0
    section = None

    while i < n:
        line = lines[i]

        # --- セクション切り替え ---
        if line == '技':
            section = 'moves'; i += 1; continue
        if line == '特性':
            section = 'abilities'; i += 1; continue
        if line == '能力補正':
            section = 'natures'; i += 1; continue
        if line == '持ち物':
            section = 'items'; i += 1; continue
        if line == '能力ポイント':
            section = 'sp'; i += 1; continue
        if line in ('使用率データ', '構築記事', 'シーズン選択'):
            section = None; i += 1; continue

        # ==================== 技 ====================
        # パターン: 名前 / 数値 / %
        if section == 'moves':
            if len(result['moves']) >= 10:
                i += 1; continue
            # 名前行の次が数値、その次が"%"であることを確認
            if i + 2 < n and re.match(r'^[\d.]+$', lines[i+1]) and lines[i+2] == '%':
                name = line
                if name and name not in result['moves']:
                    result['moves'].append(name)
                i += 3
                continue
            i += 1
            continue

        # ==================== 特性 ====================
        # パターン: 連番 / 名前 / XX.X% / XX.X%
        if section == 'abilities':
            if len(result['abilities']) >= 3:
                i += 1; continue
            if re.match(r'^\d+$', line):
                # 連番の次が名前、その次に%表記
                if i + 2 < n and re.match(r'^[\d.]+%$', lines[i+2]):
                    name = lines[i+1]
                    if name and name not in result['abilities']:
                        result['abilities'].append(name)
                    i += 4  # 連番,名前,%,% の4行
                    continue
            i += 1
            continue

        # ==================== 能力補正（性格） ====================
        # パターン: 連番 / 名前 / ( / 上昇 / 下降 / ) / XX.X% / XX.X%
        # ニュートラル性格の場合は ( ) 部分がないことがある
        if section == 'natures':
            if len(result['natures']) >= 3:
                i += 1; continue
            if re.match(r'^\d+$', line):
                name = lines[i+1] if i+1 < n else None
                if name and re.match(r'^[ぁ-んー]+$', name):
                    j = i + 2
                    # 括弧がある場合はスキップ
                    if j < n and lines[j] == '(':
                        # ( 上昇 下降 ) を読み飛ばす
                        j += 1
                        while j < n and lines[j] != ')':
                            j += 1
                        j += 1  # ')' の次へ
                    # ここでパーセントのはず
                    if j < n and re.match(r'^[\d.]+%$', lines[j]):
                        if name not in result['natures']:
                            result['natures'].append(name)
                        i = j + 2  # %,% の2行分進める
                        continue
            i += 1
            continue

        # ==================== 持ち物 ====================
        # パターン: 連番 / 名前 / XX.X% / XX.X%
        if section == 'items':
            if len(result['items']) >= 5:
                i += 1; continue
            if re.match(r'^\d+$', line):
                if i + 2 < n and re.match(r'^[\d.]+%$', lines[i+2]):
                    name = lines[i+1]
                    if name and name not in result['items']:
                        result['items'].append(name)
                    i += 4
                    continue
            i += 1
            continue

        # ==================== 能力ポイント ====================
        # 「合算」セクションはスキップし、「個別」の最初の1件のみ取得
        # パターン(個別1件目): 連番 / 略称(AS等) / XX.X% / H 数値? / A 数値? / B 数値? / C 数値? / D 数値? / S 数値?
        if section == 'sp':
            if line == '合算':
                i += 1; continue
            if line == '個別':
                i += 1; continue
            if result['topSp'] is not None:
                i += 1; continue
            if re.match(r'^\d+$', line):
                # 連番の後: 略称、%、そしてH/A/B/C/D/Sの実数値羅列
                j = i + 1
                if j < n and re.match(r'^[HABCDShabcds]+$', lines[j]):
                    j += 1  # 略称スキップ
                    if j < n and re.match(r'^[\d.]+%$', lines[j]):
                        j += 1  # %スキップ
                        sp = {"h":0,"a":0,"b":0,"c":0,"d":0,"s":0}
                        # H 2 A 32 S 32 のように 文字/数値 が交互に並ぶ
                        while j + 1 < n and lines[j] in ('H','A','B','C','D','S') and re.match(r'^\d+$', lines[j+1]):
                            sp[lines[j].lower()] = int(lines[j+1])
                            j += 2
                        total = sum(sp.values())
                        if 1 <= total <= 128:
                            result['topSp'] = sp
                        i = j
                        continue
            i += 1
            continue

        i += 1

    return result

def get_latest_season():
    """最新シーズン番号を自動取得"""
    html = fetch_html(f"{BASE}/pokemon/list?rule=0")
    if not html:
        return SEASON
    seasons = re.findall(r'season=(\d+)', html)
    if seasons:
        return max(int(s) for s in seasons)
    return SEASON

def main():
    print("=== champs.pokedb.tokyo から使用率データ取得 ===\n")

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

        html = fetch_html(url)
        if html is None:
            print("スキップ")
            continue

        lines = get_lines(html)
        data = parse_pokemon(lines)
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
