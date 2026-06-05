#!/usr/bin/env python3
"""
pokemon_base.json + pokemon_moves.json + move_db.json を結合し
index.html に貼り付け可能な形式で出力する

使用方法:
  python build_db.py

入力:
  pokemon_base.json   ← collect_pokemon_base.py の出力
  pokemon_moves.json  ← collect_pokemon_moves.py の出力
  move_db.json        ← collect_move_db.py の出力

出力:
  pokemon_db_output.txt ← index.html の該当箇所に貼り付け
"""

import json
import re
import os

def load_json(path):
    if not os.path.exists(path):
        print(f"WARNING: {path} が見つかりません（スキップ）")
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def clean_name(name):
    name = re.sub(r'([A-Z])M$', r'\1', name)
    name = re.sub(r'(?<=[^\x00-\x7F])M$', '', name)
    return name.strip()

def main():
    base_list   = load_json('pokemon_base.json')
    moves_dict  = load_json('pokemon_moves.json') or {}
    move_db     = load_json('move_db.json') or {}
    usage_dict  = load_json('pokemon_usage.json') or {}

    if base_list is None:
        print('ERROR: pokemon_base.json が必須です')
        return

    # POKEMON_DB 構築
    entries = []
    moves_matched = 0
    moves_missing = 0

    for p in base_list:
        name = clean_name(p['name'])
        entry = {
            'name': name,
            'hp':   p.get('hp',  0),
            'atk':  p.get('atk', 0),
            'def':  p.get('def', 0),
            'spa':  p.get('spa', 0),
            'spd':  p.get('spd', 0),
            'spe':  p.get('spe', 0),
            't1':   p.get('t1',  ''),
            't2':   p.get('t2',  ''),
        }
        if p.get('abilities'):
            entry['abilities'] = p['abilities']
        if name in moves_dict:
            entry['moves'] = moves_dict[name]
            moves_matched += 1
        else:
            moves_missing += 1
        # 持ち物・性格の使用率TOP3
        if name in usage_dict:
            u = usage_dict[name]
            if u.get('items'):   entry['topItems']   = u['items'][:3]
            if u.get('natures'): entry['topNatures']  = u['natures'][:3]
        entries.append(entry)

    # JavaScript 出力
    lines = []
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')
    lines.append(f'const DB_UPDATED="{today}";')
    lines.append('')
    lines.append('// ============================================================')
    lines.append('// POKEMON_DB + MOVE_DB')
    lines.append('// このブロックをまるごと index.html の該当箇所に貼り付けてください')
    lines.append('// ============================================================')
    lines.append('')

    lines.append('const POKEMON_DB=[')
    for i, e in enumerate(entries):
        comma = ',' if i < len(entries) - 1 else ''
        parts = [
            f'"name":{json.dumps(e["name"], ensure_ascii=False)}',
            f'"hp":{e["hp"]}',
            f'"atk":{e["atk"]}',
            f'"def":{e["def"]}',
            f'"spa":{e["spa"]}',
            f'"spd":{e["spd"]}',
            f'"spe":{e["spe"]}',
            f'"t1":{json.dumps(e["t1"], ensure_ascii=False)}',
            f'"t2":{json.dumps(e["t2"], ensure_ascii=False)}',
        ]
        if 'abilities' in e:
            parts.append(f'"abilities":{json.dumps(e["abilities"], ensure_ascii=False)}')
        if 'moves' in e:
            parts.append(f'"moves":{json.dumps(e["moves"], ensure_ascii=False)}')
        lines.append('{' + ','.join(parts) + '}' + comma)
    lines.append('];')
    lines.append('')

    if move_db:
        lines.append('const MOVE_DB={')
        items = list(move_db.items())
        for i, (k, v) in enumerate(items):
            comma = ',' if i < len(items) - 1 else ''
            lines.append(f'{json.dumps(k, ensure_ascii=False)}:{json.dumps(v, ensure_ascii=False)}{comma}')
        lines.append('};')
    else:
        lines.append('const MOVE_DB={};')

    output = '\n'.join(lines)
    with open('pokemon_db_output.txt', 'w', encoding='utf-8') as f:
        f.write(output)

    print(f'✓ pokemon_db_output.txt 生成')
    print(f'  POKEMON_DB: {len(entries)}体')
    print(f'    技データあり: {moves_matched}体')
    print(f'    技データなし: {moves_missing}体')
    print(f'  MOVE_DB: {len(move_db)}技')
    usage_count = sum(1 for p in entries if 'topItems' in p or 'topNatures' in p)
    print(f'  使用率データ: {usage_count}体')
    print()
    print('【貼り付け手順】')
    print('  index.html の const POKEMON_DB=[ から const MOVE_DB={ ... }; まで')
    print('  pokemon_db_output.txt の内容で置き換えてください')

    # サンプル表示
    print('\nサンプル（先頭3件）:')
    for e in entries[:3]:
        ab = e.get('abilities', [])
        mv = e.get('moves', [])
        print(f"  {e['name']}: HP{e['hp']} A{e['atk']} B{e['def']} C{e['spa']} D{e['spd']} S{e['spe']}")
        print(f"    t1={e['t1']} t2={e['t2']} abilities={ab} moves={mv[:2]}{'...' if len(mv)>2 else ''}")

if __name__ == '__main__':
    main()
