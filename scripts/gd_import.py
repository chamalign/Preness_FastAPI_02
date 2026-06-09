#!/usr/bin/env python3
"""
Google Drive の生成済み問題ファイルをショートコードで投入するスクリプト.

サブコマンド:
  practice <section> <num>   セクション別の練習問題を 1 ファイル投入
  mock [--kind full|diag]    実力診断 模擬試験の全 6 パートを投入
  list [section]             利用可能なファイル番号の一覧を表示

セクションコード (practice / list 用):
  la  Listening A    lb  Listening B    lc  Listening C
  ga  Grammar A      gb  Grammar B      rd  Reading

使用例:
  python scripts/gd_import.py practice la 1
  python scripts/gd_import.py practice rd 3
  python scripts/gd_import.py mock
  python scripts/gd_import.py --dry-run practice ga 2
  python scripts/gd_import.py list
  python scripts/gd_import.py list la

~/.zshrc にエイリアスを設定すると短く実行できる:
  export GD="$HOME/Library/CloudStorage/Box-Box/buruhamuhamu/Preness/Complitedver_FastAPI/FastAPI/scripts/gd_import.py"
  alias gd='python "$GD"'

  gd practice la 1
  gd mock
  gd list
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# ── Google Drive ベースパス ────────────────────────────────────────────────────
_GD_GENERATED = Path(
    "/Users/buruhamuhamu/Library/CloudStorage/"
    "GoogleDrive-kyoya.sasaki2027@gmail.com/"
    ".shortcut-targets-by-id/"
    "1B4hLNZCgAxW2SitvbUHdbY3ZD084K7NC/"
    "Preness/04_試験問題コンテンツ/問題生成/生成済み問題"
)
_SECTION_DIR = _GD_GENERATED / "セクション別"
_MOCK_DIR    = _GD_GENERATED / "実力診断 模擬試験"

# ── セクションコード → (フォルダ名, ファイル名中のセクション名) ─────────────────
_SECTION_MAP: dict[str, tuple[str, str]] = {
    "la": ("Listening_A", "Listening A"),
    "lb": ("Listening_B", "Listening B"),
    "lc": ("Listening_C", "Listening C"),
    "ga": ("Grammar_A",   "Grammar A"),
    "gb": ("Grammar_B",   "Grammar B"),
    "rd": ("Reading",     "Reading"),
}


# ── 内部ユーティリティ ──────────────────────────────────────────────────────────

def _read_api_key(api_key: Optional[str]) -> str:
    if api_key:
        return api_key
    env = os.getenv("CONTENT_SOURCE_API_KEY", "").strip()
    if not env:
        raise SystemExit("CONTENT_SOURCE_API_KEY が未設定です. --api-key または環境変数で指定してください.")
    return env


def _post_json(*, base_url: str, api_key: str, endpoint: str, payload: dict, timeout_s: float = 300.0) -> Any:
    import httpx
    url = base_url.rstrip("/") + endpoint
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(url, headers=headers, json=payload)
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text}


def _resolve_practice_path(section: str, num: int) -> Path:
    if section not in _SECTION_MAP:
        raise SystemExit(
            f"不明なセクションコード: {section!r}\n"
            f"使用可能: {', '.join(_SECTION_MAP)}"
        )
    dir_name, section_name = _SECTION_MAP[section]
    filename = f"セクション別 {section_name}_{num:04d}.txt"
    return _SECTION_DIR / dir_name / filename


# ── サブコマンド実装 ───────────────────────────────────────────────────────────

def cmd_practice(args: argparse.Namespace) -> None:
    from app.services.hand_made_importer import build_practice_part_payload_from_file

    file_path = _resolve_practice_path(args.section, args.num)
    if not file_path.exists():
        raise SystemExit(
            f"ファイルが見つかりません:\n  {file_path}\n\n"
            f"利用可能なファイルを確認: python scripts/gd_import.py list {args.section}"
        )

    payload = build_practice_part_payload_from_file(file_path)
    print(f"[投入] {file_path.name}  (part_type: {payload['part_type']})")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    out = _post_json(
        base_url=args.base_url,
        api_key=_read_api_key(args.api_key),
        endpoint="/api/v1/import/practice",
        payload=payload,
    )
    print(out)


def cmd_mock(args: argparse.Namespace) -> None:
    from app.services.hand_made_importer import build_full_parts_payload

    if not _MOCK_DIR.is_dir():
        raise SystemExit(f"実力診断 模擬試験 ディレクトリが見つかりません:\n  {_MOCK_DIR}")

    kind     = "full" if args.kind == "full" else "short"
    endpoint = "/api/v1/import/full_mock" if args.kind == "full" else "/api/v1/import/diagnostics"

    payload = build_full_parts_payload(_MOCK_DIR, kind=kind, title=args.title)
    print(f"[投入] 実力診断 模擬試験  (kind={kind}, endpoint={endpoint})")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    out = _post_json(
        base_url=args.base_url,
        api_key=_read_api_key(args.api_key),
        endpoint=endpoint,
        payload=payload,
    )
    print(out)


def cmd_list(args: argparse.Namespace) -> None:
    sections = [args.section] if args.section else list(_SECTION_MAP)
    for sec in sections:
        if sec not in _SECTION_MAP:
            print(f"[警告] 不明なセクションコード: {sec}")
            continue
        dir_name, section_name = _SECTION_MAP[sec]
        sec_dir = _SECTION_DIR / dir_name
        if not sec_dir.is_dir():
            print(f"[{sec}] ディレクトリなし: {sec_dir}")
            continue
        files = sorted(sec_dir.glob("*.txt"))
        print(f"\n[{sec}] {dir_name} — {len(files)} ファイル")
        for f in files:
            # ファイル名から番号を抽出して表示
            num_str = f.stem.rsplit("_", 1)[-1]
            print(f"  {num_str}  {f.name}")
    # 実力診断 模擬試験
    if not args.section:
        print(f"\n[mock] 実力診断 模擬試験")
        if _MOCK_DIR.is_dir():
            for f in sorted(_MOCK_DIR.glob("*.txt")):
                print(f"  {f.name}")
        else:
            print(f"  ディレクトリなし: {_MOCK_DIR}")


# ── CLI 定義 ─────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Google Drive 生成済み問題をショートコードで投入する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
        help="API ベース URL (環境変数 BASE_URL でも設定可)",
    )
    parser.add_argument("--api-key", default=None, help="Bearer トークン (env: CONTENT_SOURCE_API_KEY)")
    parser.add_argument("--dry-run", action="store_true", help="payload JSON を表示して POST しない")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # practice
    p = sub.add_parser("practice", help="セクション別の練習問題を 1 ファイル投入")
    p.add_argument(
        "section",
        choices=list(_SECTION_MAP),
        metavar="section",
        help=f"セクションコード: {', '.join(_SECTION_MAP)}",
    )
    p.add_argument("num", type=int, help="ファイル番号 (例: 1 → 0001)")
    p.set_defaults(func=cmd_practice)

    # mock
    m = sub.add_parser("mock", help="実力診断 模擬試験の全 6 パートを投入")
    m.add_argument(
        "--kind",
        choices=["full", "diag"],
        default="full",
        help="投入先エンドポイント: full=full_mock, diag=diagnostics (デフォルト: full)",
    )
    m.add_argument("--title", default=None, help="タイトルの上書き (省略時: ディレクトリ名)")
    m.set_defaults(func=cmd_mock)

    # list
    ls = sub.add_parser("list", help="利用可能なファイル一覧を表示")
    ls.add_argument(
        "section",
        nargs="?",
        default=None,
        choices=list(_SECTION_MAP),
        metavar="section",
        help=f"セクションコード (省略時: 全セクション): {', '.join(_SECTION_MAP)}",
    )
    ls.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
