"""FM06 Long3 + Short2 を 1 本にマージ (S, L, S, L, L 順)."""

from typing import Any, Dict


def merge_fm06(long3_data: Dict[str, Any], short2_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Long3 と Short2 の passages を short, long, short, long, long の順で 1 つにまとめる.
    ファイル I/O は行わず、dict のみを扱う.
    """
    long_passages = long3_data.get("passages", [])
    short_passages = short2_data.get("passages", [])

    if len(long_passages) < 3:
        raise ValueError(f"Long3 は 3 本必要です (got {len(long_passages)})")
    if len(short_passages) < 2:
        raise ValueError(f"Short2 は 2 本必要です (got {len(short_passages)})")

    merged = [
        short_passages[0],
        short_passages[1],
        long_passages[0],
        long_passages[1],
        long_passages[2],
    ]
    return {"passages": merged}
