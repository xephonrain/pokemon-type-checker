#!/usr/bin/env python3
"""
pokemon_usage.json を GitHub API でリポジトリにプッシュするスクリプト
VPS（Windows Server）上で実行する

使用方法:
  1. GITHUB_TOKEN に Personal Access Token（repo権限）を設定
  2. python push_usage_to_github.py

前提:
  - collect_pokemon_usage.py を先に実行して pokemon_usage.json を生成しておく
  - GitHub PAT が repo スコープを持っていること
"""

import json, base64, urllib.request, urllib.error, os, sys
from datetime import datetime, timezone, timedelta

# ============================================================
# 設定（環境変数から取得 or 直接書き換えてください）
# ============================================================
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "ghp_ここにトークンを入力")
REPO_OWNER   = "xephonrain"
REPO_NAME    = "pokemon-type-checker"
BRANCH       = "main"

# プッシュするファイルのパス（リポジトリ内のパス）
REMOTE_PATH  = "pokemon_usage.json"
# ローカルファイルのパス（このスクリプトと同じディレクトリ）
LOCAL_PATH   = os.path.join(os.path.dirname(__file__), "pokemon_usage.json")

JST = timezone(timedelta(hours=9))

# ============================================================
# GitHub API ヘルパー
# ============================================================
def api_request(method, path, data=None):
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "pokemon-battle-live-updater/1.0",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        print(f"HTTP Error {e.code}: {err}")
        raise

def get_file_sha(remote_path):
    """既存ファイルのSHAを取得（更新に必要）。存在しない場合はNoneを返す（新規作成扱い）"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{remote_path}?ref={BRANCH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "pokemon-battle-live-updater/1.0",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8")).get("sha")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # ファイルが存在しない（新規作成のため正常）
        raise

def push_file(local_path, remote_path, commit_message):
    """ファイルをGitHubリポジトリにプッシュ"""
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    sha = get_file_sha(remote_path)
    data = {
        "message": commit_message,
        "content": content,
        "branch": BRANCH,
    }
    if sha:
        data["sha"] = sha  # 既存ファイルの更新には SHA が必要

    res = api_request("PUT", f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{remote_path}", data)
    return res

# ============================================================
# メイン処理
# ============================================================
def main():
    print("=== pokemon_usage.json → GitHub プッシュ ===\n")

    # トークン確認
    if GITHUB_TOKEN.startswith("ghp_ここに"):
        print("ERROR: GITHUB_TOKEN が設定されていません")
        print("  環境変数 GITHUB_TOKEN を設定するか、スクリプト内の GITHUB_TOKEN を書き換えてください")
        sys.exit(1)

    # ローカルファイル確認
    if not os.path.exists(LOCAL_PATH):
        print(f"ERROR: {LOCAL_PATH} が見つかりません")
        print("  先に collect_pokemon_usage.py を実行してください")
        sys.exit(1)

    # ファイルサイズとポケモン数を確認
    with open(LOCAL_PATH, encoding="utf-8") as f:
        usage = json.load(f)
    poke_count = len(usage)
    has_data   = sum(1 for v in usage.values() if v.get("moves"))
    file_size  = os.path.getsize(LOCAL_PATH) // 1024
    print(f"ローカルファイル: {poke_count}体 (データあり: {has_data}体) {file_size}KB")

    if has_data == 0:
        print("WARNING: 全ポケモンのデータが空です。パーサーの修正が必要な可能性があります。")
        print("空データのままプッシュします...")

    # コミットメッセージ
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    commit_msg = f"chore: pokemon_usage.json 自動更新 {now_jst}"

    print(f"\nプッシュ先: {REPO_OWNER}/{REPO_NAME}/{REMOTE_PATH} ({BRANCH})")
    print(f"コミット: {commit_msg}")
    print("プッシュ中...")

    try:
        res = push_file(LOCAL_PATH, REMOTE_PATH, commit_msg)
        commit_sha = res.get("commit", {}).get("sha", "")[:8]
        print(f"\n完了！ コミット: {commit_sha}")
        print(f"  URL: https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/{BRANCH}/{REMOTE_PATH}")
    except Exception as e:
        print(f"\nERROR: プッシュに失敗しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
