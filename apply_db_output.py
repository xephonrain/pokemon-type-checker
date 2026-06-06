#!/usr/bin/env python3
"""
build_db.py が出力した pokemon_db_output.txt を
pokemon_type_checker.html に自動反映するスクリプト

使い方:
  python apply_db_output.py

  # HTMLファイルを指定する場合
  python apply_db_output.py --html index.html
"""

import sys, os, re, argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--txt',  default='pokemon_db_output.txt')
    parser.add_argument('--html', default='index.html')
    args = parser.parse_args()

    if not os.path.exists(args.txt):
        print(f"ERROR: {args.txt} が見つかりません")
        print("先に build_db.py を実行してください")
        sys.exit(1)

    if not os.path.exists(args.html):
        print(f"ERROR: {args.html} が見つかりません")
        sys.exit(1)

    with open(args.txt, encoding='utf-8') as f:
        new_block = f.read()

    with open(args.html, encoding='utf-8') as f:
        html = f.read()

    # POKEMON_DB の開始位置
    start = html.find('const POKEMON_DB=[')
    if start == -1:
        print("ERROR: POKEMON_DB が見つかりません")
        sys.exit(1)

    # MOVE_DB の終了位置
    move_db_end = html.find('};', html.find('const MOVE_DB='))
    if move_db_end == -1:
        # MOVE_DB が {} の場合
        move_db_end = html.find('const MOVE_DB={}')
        if move_db_end == -1:
            print("ERROR: MOVE_DB の終端が見つかりません")
            sys.exit(1)
        end = move_db_end + len('const MOVE_DB={}')
    else:
        end = move_db_end + 2  # "};" の後

    # pokemon_db_output.txt からコメント行を除いたブロックを抽出
    lines = new_block.split('\n')
    block_lines = [l for l in lines if not l.startswith('//') and l.strip() != '']
    new_db_block = '\n'.join(block_lines)

    # バックアップ
    bak = args.html + '.bak'
    with open(bak, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"バックアップ: {bak}")

    # 差し替え + DB_UPDATED を反映
    import re as _re
    db_updated_m = _re.search(r'const DB_UPDATED="([^"]+)";', new_db_block)
    new_html = html[:start] + new_db_block + '\n' + html[end:]
    if db_updated_m:
        updated_val = db_updated_m.group(1)
        new_html = _re.sub(r'const DB_UPDATED="[^"]*";', f'const DB_UPDATED="{updated_val}";', new_html, count=1)
        print(f"DB更新日: {updated_val}")
    with open(args.html, 'w', encoding='utf-8') as f:
        f.write(new_html)

    # 確認
    import json
    db_start = new_html.find('const POKEMON_DB=[')
    db_end   = new_html.find('];', db_start) + 2
    db_str   = new_html[db_start + len('const POKEMON_DB='):db_end-1]
    db_str   = db_str[db_str.find('['):]
    db = json.loads(db_str)
    print(f"✅ {args.html} を更新しました（{len(db)}体）")

    # サンプル確認
    sample = next((p for p in db if p['name'] == 'カバルドン'), db[0])
    print(f"\nサンプル: {sample['name']}: H{sample['hp']} A{sample['atk']} B{sample['def']} C{sample['spa']} D{sample['spd']} S{sample['spe']}")

if __name__ == '__main__':
    main()
