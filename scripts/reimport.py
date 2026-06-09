"""
Rails DB 削除後の再投入スクリプト.

使い方:
  python scripts/reimport.py mock <job_id>
  python scripts/reimport.py exercise <part_type> <job_id>
  python scripts/reimport.py diagnostic <job_id>

outputs/ に保存済みの Rails payload を読み込み POST するだけ.
TTS・S3 アップロードは一切行わない.
"""

import json
import sys
from pathlib import Path

# FastAPI ルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rails_client import (
    post_diagnostic_to_rails,
    post_exercise_to_rails,
    post_mock_to_rails,
)

OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"


def _load(filename: str) -> dict:
    path = OUTPUTS_DIR / f"{filename}.json"
    if not path.exists():
        print(f"[ERROR] ファイルが見つかりません: {path}")
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def reimport_mock(job_id: str) -> None:
    payload = _load(f"mock_{job_id}")
    post_mock_to_rails(payload)
    print(f"[OK] mock 再投入完了: job_id={job_id}")


def reimport_diagnostic(job_id: str) -> None:
    payload = _load(f"diagnostic_{job_id}")
    post_diagnostic_to_rails(payload)
    print(f"[OK] diagnostic 再投入完了: job_id={job_id}")


def reimport_exercise(part_type: str, job_id: str) -> None:
    payload = _load(f"exercise_{part_type}_{job_id}")
    post_exercise_to_rails(payload)
    print(f"[OK] exercise 再投入完了: part_type={part_type} job_id={job_id}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    kind = args[0]
    if kind == "mock" and len(args) == 2:
        reimport_mock(args[1])
    elif kind == "diagnostic" and len(args) == 2:
        reimport_diagnostic(args[1])
    elif kind == "exercise" and len(args) == 3:
        reimport_exercise(args[1], args[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
