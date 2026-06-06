#!/usr/bin/env python3
"""
build_db.py が出力した pokemon_db_output.txt を
index.html に自動反映するスクリプト

使い方:
  python apply_db_output.py
  python apply_db_output.py --html index.html
"""

import sys, os, re, json, argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--txt',  default='pokemon_db_output.txt')
    parser.add_argument('--html', default='index.html')
    args = parser.parse_args()

    if not os.path.exists(args.txt):
        print(f"ERROR: {args.txt} が見つかりません")
        sys.exit(1)

    if not os.path.exists(args.html):
        print(f"ERROR: {args.html} が見つかりません")
        sys.exit(1)

    with open(args.txt, encoding='utf-8') as f:
        txt = f.read()

    with open(args.html, encoding='utf-8') as f:
        html = f.read()

    # ============================================================
    # pokemon_db_output.txt から POKEMON_DB と MOVE_DB を抽出
    # ============================================================
    db_match   = re.search(r'(const POKEMON_DB=\[.*?\];)', txt, re.DOTALL)
    move_match = re.search(r'(const MOVE_DB=\{.*?\};)', txt, re.DOTALL)
    date_match = re.search(r'const DB_UPDATED="([^"]+)";', txt)

    if not db_match:
        print("ERROR: pokemon_db_output.txt に POKEMON_DB が見つかりません")
        sys.exit(1)
    if not move_match:
        print("ERROR: pokemon_db_output.txt に MOVE_DB が見つかりません")
        sys.exit(1)

    new_pokemon_db = db_match.group(1)
    new_move_db    = move_match.group(1)

    # ============================================================
    # HTML内の POKEMON_DB を差し替え
    # ============================================================
    # POKEMON_DB の範囲: "const POKEMON_DB=[" から "];" まで
    db_start = html.find('const POKEMON_DB=[')
    if db_start == -1:
        print("ERROR: HTMLに POKEMON_DB が見つかりません")
        sys.exit(1)
    db_end = html.find('];', db_start) + 2

    html = html[:db_start] + new_pokemon_db + html[db_end:]

    # ============================================================
    # HTML内の MOVE_DB を差し替え
    # ============================================================
    move_start = html.find('const MOVE_DB={')
    if move_start == -1:
        print("ERROR: HTMLに MOVE_DB が見つかりません")
        sys.exit(1)
    # MOVE_DB の終端: "const MOVE_DB={" の位置から最初の "};" を探す
    move_end = html.find('};', move_start) + 2

    html = html[:move_start] + new_move_db + html[move_end:]

    # ============================================================
    # DB_UPDATED を更新
    # ============================================================
    if date_match:
        updated = date_match.group(1)
        html = re.sub(r'const DB_UPDATED="[^"]*";', f'const DB_UPDATED="{updated}";', html, count=1)
        print(f"DB更新日: {updated}")

    # ============================================================
    # バックアップ & 書き込み
    # ============================================================
    bak = args.html + '.bak'
    with open(bak, 'w', encoding='utf-8') as f:
        # バックアップは元のhtmlを保存（変数htmlは既に変更済みなので元ファイルを再読込）
        with open(args.html, encoding='utf-8') as orig:
            f.write(orig.read())
    print(f"バックアップ: {bak}")

    with open(args.html, 'w', encoding='utf-8') as f:
        f.write(html)

    # ============================================================
    # 確認
    # ============================================================
    db_s = html.find('const POKEMON_DB=[')
    db_e = html.find('];', db_s) + 2
    db   = json.loads(html[db_s + len('const POKEMON_DB='):db_e-1])
    print(f"✅ {args.html} を更新しました（{len(db)}体）")
    sample = next((p for p in db if p['name'] == 'カバルドン'), db[0])
    print(f"サンプル: {sample['name']}: H{sample['hp']} A{sample['atk']} B{sample['def']} C{sample['spa']} D{sample['spd']} S{sample['spe']}")

if __name__ == '__main__':
    main()
