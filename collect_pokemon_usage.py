#!/usr/bin/env python3
"""
ポケモンチャンピョンズ 使用率データ収集
取得元: https://champs.pokedb.tokyo
方式: Playwright（JS動的レンダリング対応）

使用方法:
  pip install playwright
  playwright install chromium
  python collect_pokemon_usage.py

出力:
  pokemon_usage.json
"""

import asyncio, json, re, time, os
from playwright.async_api import async_playwright

BASE = "https://champs.pokedb.tokyo"

def parse_sp(text):
    """H 2 A 32 S 32 → {"h":2,"a":32,"s":32,...}"""
    sp = {"h":0,"a":0,"b":0,"c":0,"d":0,"s":0}
    for k, v in re.findall(r'([HABCDShabcds])\s+(\d+)', text):
        sp[k.lower()] = int(v)
    return sp

async def get_poke_list(page):
    """ランキング一覧から全ポケモンのID・名前を取得"""
    print("ポケモン一覧取得中...")
    await page.goto(f"{BASE}/pokemon/list?rule=0", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    # aタグからポケモンIDを収集
    links = await page.query_selector_all('a[href*="/pokemon/show/"]')
    pokemons = []
    seen = set()
    for a in links:
        href = await a.get_attribute('href')
        text = (await a.inner_text()).strip()
        m = re.search(r'/pokemon/show/([0-9]+-[0-9]+)', href or '')
        if not m:
            continue
        pid = m.group(1)
        if pid in seen:
            continue
        seen.add(pid)
        name = re.sub(r'^\d+\s*', '', text).strip()
        if name:
            pokemons.append({'id': pid, 'name': name})

    print(f"  {len(pokemons)}体取得")
    return pokemons

async def parse_pokemon(page, pid, name):
    """個別ページから使用率データを取得"""
    url = f"{BASE}/pokemon/show/{pid}?rule=0"
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    text = await page.inner_text('body')
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    result = {'moves': [], 'abilities': [], 'natures': [], 'items': [], 'topSp': None}

    # 技
    in_sec = False
    for line in lines:
        if line == '技':
            in_sec = True
            continue
        if in_sec:
            if line in ['特性', '能力補正', '持ち物', '能力ポイント']:
                break
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m:
                result['moves'].append(m.group(1))
                if len(result['moves']) >= 10:
                    break

    # 特性
    in_sec = False
    for line in lines:
        if line == '特性':
            in_sec = True
            continue
        if in_sec:
            if line in ['能力補正', '持ち物', '能力ポイント', '技']:
                break
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m and not re.match(r'^\d+$', m.group(1)):
                result['abilities'].append(m.group(1))
                if len(result['abilities']) >= 3:
                    break

    # 性格
    in_sec = False
    for line in lines:
        if line == '能力補正':
            in_sec = True
            continue
        if in_sec:
            if line in ['持ち物', '能力ポイント', '技', '特性']:
                break
            m = re.match(r'^([ぁ-ん]+)\s*\(.*?\)\s+([\d.]+)%$', line)
            if m:
                result['natures'].append(m.group(1))
                if len(result['natures']) >= 3:
                    break

    # 持ち物
    in_sec = False
    for line in lines:
        if line == '持ち物':
            in_sec = True
            continue
        if in_sec:
            if line in ['能力ポイント', '技', '特性', '能力補正']:
                break
            m = re.match(r'^(.+?)\s+([\d.]+)%$', line)
            if m and not re.match(r'^\d+$', m.group(1)):
                result['items'].append(m.group(1))
                if len(result['items']) >= 5:
                    break

    # 能力ポイント（個別TOP1）
    in_sec = False
    for line in lines:
        if '能力ポイント' in line:
            in_sec = True
            continue
        if in_sec:
            if re.search(r'[HABCDShabcds]\s+\d+', line):
                sp = parse_sp(line)
                total = sum(sp.values())
                if 1 <= total <= 128:
                    result['topSp'] = sp
                    break

    return result

async def main():
    print("=== champs.pokedb.tokyo から使用率データ取得 ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 一覧取得
        pokemons = await get_poke_list(page)
        if not pokemons:
            print("ERROR: ポケモン一覧が取得できません")
            await browser.close()
            return

        result = {}
        total = len(pokemons)

        for idx, poke in enumerate(pokemons):
            pid = poke['id']
            name = poke['name']
            print(f"[{idx+1}/{total}] {name} ({pid}) ...", end=" ", flush=True)

            try:
                data = await parse_pokemon(page, pid, name)
                result[name] = data
                moves_str = ",".join(data['moves'][:3]) if data['moves'] else "なし"
                items_str = ",".join(data['items'][:2]) if data['items'] else "なし"
                sp_str    = str(data['topSp']) if data['topSp'] else "なし"
                print(f"技:{moves_str} 持:{items_str} SP:{sp_str}")
            except Exception as e:
                print(f"エラー: {e}")
                result[name] = {'moves':[],'abilities':[],'natures':[],'items':[],'topSp':None}

            await asyncio.sleep(1.0)

        await browser.close()

    with open("pokemon_usage.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ pokemon_usage.json 保存: {len(result)}体")

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
    asyncio.run(main())
