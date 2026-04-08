"""
hand_made/*.txt (GPT 中間形式) を FastAPI import API 用 payload に変換する。

このモジュールは音声合成や DB 保存は行わず、txt -> dict/payload のみを担当する。
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence


REPO_ROOT_MARKER_DIR = ".venv-py313"


def _find_repo_root(start: Path | None = None) -> Path:
    """scripts/ や app/ からでもリポジトリ直下に辿り着くための簡易推定。"""
    if start is None:
        start = Path(__file__).resolve()
    cur = start
    for _ in range(10):
        if (cur / REPO_ROOT_MARKER_DIR).is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    # 最後の手段: このファイルから 3 階層戻る
    return Path(__file__).resolve().parents[3]


def load_json_txt(path: Path) -> Dict[str, Any]:
    """
    hand_made の .txt を JSON として読み込む。

    期待: すでに JSON 形式（null, [] , {}）になっていること。
    """
    # まれに UTF-8 BOM 付き .txt があるため utf-8-sig で吸収する
    raw = path.read_text(encoding="utf-8-sig").strip()
    sanitized = _sanitize_newlines_in_json_strings(raw)

    try:
        obj = json.loads(sanitized)
        if not isinstance(obj, dict):
            raise ValueError("top-level JSON must be an object")
        return obj
    except json.JSONDecodeError:
        # 複数 JSON オブジェクトが末尾で連結されている場合等に備える。
        # ここでは "top-level dict を1つ返す" を最優先に、候補を抽出してマージする。
        objects = _extract_top_level_json_objects(sanitized)
        if not objects:
            raise

        parsed: list[dict[str, Any]] = []
        for s in objects:
            o = json.loads(s)
            if not isinstance(o, dict):
                continue
            parsed.append(o)

        if not parsed:
            raise
        if len(parsed) == 1:
            return parsed[0]
        return _merge_dicts_by_primary_list_key(parsed)


def _sanitize_newlines_in_json_strings(text: str) -> str:
    """
    JSON の文字列内に生改行が入っていると json.loads が落ちる。
    そこで「ダブルクォートで囲まれている領域」内の改行等を JSON で許容されるエスケープに変換する。
    """
    out: list[str] = []
    in_str = False
    escape = False

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if escape:
                out.append(ch)
                escape = False
                i += 1
                continue
            if ch == "\\":
                out.append(ch)
                escape = True
                i += 1
                continue
            if ch == '"':
                # 現状のファイルには string 中に未エスケープの " が紛れていることがある
                # 例: question_text: "The word "lucrative" in line 4 ..."
                # JSON 的にはこの内側の " を \" に直す必要があるので、
                # 次の非空白文字が , } ] のいずれかなら閉じクォート、それ以外は内部クォートとして扱う。
                j = i + 1
                while j < n and text[j] in " \t\r\n":
                    j += 1
                next_ch = text[j] if j < n else ""
                if next_ch in ",}]:":  # closing quote for JSON strings can be followed by :, comma, or container closers
                    out.append('"')
                    in_str = False
                else:
                    out.append('\\"')
                i += 1
                continue

            # 生の改行/タブ/キャリッジリターンを JSON で許容される表現へ
            if ch == "\n":
                out.append("\\n")
                i += 1
                continue
            if ch == "\r":
                out.append("\\r")
                i += 1
                continue
            if ch == "\t":
                out.append("\\t")
                i += 1
                continue

            out.append(ch)
            i += 1
            continue

        # in_str == False
        if ch == '"':
            out.append(ch)
            in_str = True
        else:
            out.append(ch)
        i += 1

    return "".join(out)


def _extract_top_level_json_objects(text: str) -> list[str]:
    """
    `{ ... }{ ... }` のように複数オブジェクトが連結されたケースから、top-level オブジェクト断片を抽出する。
    """
    objs: list[str] = []
    i = 0
    n = len(text)

    def skip_ws(idx: int) -> int:
        while idx < n and text[idx] in " \t\r\n,":
            idx += 1
        return idx

    while True:
        i = skip_ws(i)
        if i >= n:
            break
        if text[i] != "{":
            # top-level が { でない場合は終了（想定外のデータ）
            break

        start = i
        depth = 0
        in_str = False
        escape = False
        while i < n:
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                else:
                    if ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        objs.append(text[start:end])
                        i = end
                        break
            i += 1

        # 末尾まで辿り着けなかった場合は終了
        if i >= n and (not objs or objs[-1].count("{") != objs[-1].count("}")):
            break
    return objs


def _merge_dicts_by_primary_list_key(dicts: Sequence[dict[str, Any]]) -> Dict[str, Any]:
    """
    最上位が `{"items": [...]}` / `{"questions": [...]}` / `{"passages": [...]}` である想定で、
    複数 dict をリストキーで連結して 1 dict にまとめる。
    """
    if not dicts:
        raise ValueError("empty dicts")

    # 優先キー（この順で存在するリストを連結）
    primary_keys = ("items", "questions", "passages")
    for key in primary_keys:
        if all(isinstance(d.get(key), list) for d in dicts):
            merged: Dict[str, Any] = dict(dicts[0])
            merged[key] = []
            for d in dicts:
                merged[key].extend(d.get(key) or [])
            return merged

    # 何も合わなければ単純に先頭を返す（安全側）
    return dict(dicts[0])


@dataclass(frozen=True)
class FullMockFileSet:
    listening_part_a: Path
    listening_part_b: Path
    listening_part_c: Path
    grammar_part_a: Path
    grammar_part_b: Path
    reading: Path


def _expected_fullmock_filenames() -> Dict[str, str]:
    return {
        "listening_part_a": "01_Listening_A.txt",
        "listening_part_b": "02_Listening_B.txt",
        "listening_part_c": "03_Listening_C.txt",
        "grammar_part_a": "04_Grammar_A.txt",
        "grammar_part_b": "05_Grammar_B.txt",
        "reading": "06_Reading.txt",
    }


def infer_fullmock_fileset(set_dir: Path) -> FullMockFileSet:
    """set_dir 内の 6 ファイルを推定して返す。"""
    if not set_dir.is_dir():
        raise ValueError(f"set_dir must be a directory: {set_dir}")

    expected = _expected_fullmock_filenames()
    missing: list[str] = []
    paths: Dict[str, Path] = {}
    for part_key, filename in expected.items():
        p = set_dir / filename
        if not p.is_file():
            missing.append(filename)
        paths[part_key] = p
    if missing:
        raise ValueError(f"Missing fullmock txt files under {set_dir}: {', '.join(missing)}")

    return FullMockFileSet(
        listening_part_a=paths["listening_part_a"],
        listening_part_b=paths["listening_part_b"],
        listening_part_c=paths["listening_part_c"],
        grammar_part_a=paths["grammar_part_a"],
        grammar_part_b=paths["grammar_part_b"],
        reading=paths["reading"],
    )


def normalize_fullmock_title(dir_name: str, *, kind: str) -> str:
    """
    title はフォルダ名準拠。

    現状は `hand_made/Full_Mock/` と `hand_made/Short_Mock/` が 1 セットだが、
    将来 `Full_Mock_01, Full_Mock_02 ...` に展開する前提で、現行のベース名は _01 と解釈する。
    """
    if kind == "full" and dir_name == "Full_Mock":
        return "Full_Mock_01"
    if kind == "short" and dir_name == "Short_Mock":
        return "Short_Mock_01"
    return dir_name


def build_full_parts_payload(set_dir: Path, *, title: Optional[str] = None, kind: str) -> Dict[str, Any]:
    """FM/SM の full_parts payload を作る（POST /import/full_mock または /import/short_mock 用）。"""
    fileset = infer_fullmock_fileset(set_dir)
    full_parts: Dict[str, Any] = {
        "listening_part_a": load_json_txt(fileset.listening_part_a),
        "listening_part_b": load_json_txt(fileset.listening_part_b),
        "listening_part_c": load_json_txt(fileset.listening_part_c),
        "grammar_part_a": load_json_txt(fileset.grammar_part_a),
        "grammar_part_b": load_json_txt(fileset.grammar_part_b),
        "reading": load_json_txt(fileset.reading),
    }
    if title is None:
        title = normalize_fullmock_title(set_dir.name, kind=kind)
    return {"title": title, "full_parts": full_parts}


def _reading_file_candidates(
    *,
    reading_short_dir: Path,
    reading_long_dir: Path,
) -> list[Path]:
    candidates: list[Path] = []
    for d in (reading_short_dir, reading_long_dir):
        if not d.is_dir():
            continue
        candidates.extend(sorted([p for p in d.glob("*.txt") if p.is_file()]))
    return candidates


def _default_used_reading_record_path(repo_root: Path) -> Path:
    return repo_root / "outputs" / "used_reading.json"


def _read_used_reading_record(record_path: Path) -> set[str]:
    """
    record の破損を恐れて例外は握りつぶす。
    """
    if not record_path.is_file():
        return set()
    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    used = data.get("used", [])
    if not isinstance(used, list):
        return set()
    return {str(x) for x in used}


def _write_used_reading_record(record_path: Path, *, used_relpaths: Sequence[str]) -> None:
    record_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"used": list(used_relpaths)}
    record_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_practice_part_type_from_file(file_path: Path) -> str:
    """
    part_type をファイルの親ディレクトリから推定する。
    - Listening_A -> listening_part_a
    - Listening_B -> listening_part_b
    - Listening_C -> listening_part_c
    - Grammar_A -> grammar_part_a
    - Grammar_B -> grammar_part_b
    - Reading_Short / Reading_Long -> reading
    """
    parent = file_path.parent.name
    mapping = {
        "Listening_A": "listening_part_a",
        "Listening_B": "listening_part_b",
        "Listening_C": "listening_part_c",
        "Grammar_A": "grammar_part_a",
        "Grammar_B": "grammar_part_b",
        "Reading_Short": "reading",
        "Reading_Long": "reading",
    }
    if parent not in mapping:
        raise ValueError(f"Unsupported part source folder: {parent} ({file_path})")
    return mapping[parent]


def build_practice_part_payload_from_file(file_path: Path) -> Dict[str, Any]:
    part_type = infer_practice_part_type_from_file(file_path)
    part_data = load_json_txt(file_path)
    # listening_b などでのプレースホルダ対応（必要なもののみここで吸収する）
    if part_type == "listening_part_b" and isinstance(part_data, dict):
        part_data = _fix_listening_b_placeholders(part_data)
    return {"part_type": part_type, "part_data": part_data}


def _fix_listening_b_placeholders(part_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Listening_B/01 のみプレースホルダが残っている想定で補正する。
    - "Question [number]." -> "Question {idx}."
    - "[question_text]" -> item["question_text"]
    """
    items = part_data.get("items")
    if not isinstance(items, list):
        return part_data
    fixed_items: list[Any] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            fixed_items.append(item)
            continue
        question_text = item.get("question_text")
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        script = content.get("listening_script")
        if not isinstance(script, list):
            fixed_items.append(item)
            continue
        for turn in script:
            if not isinstance(turn, dict):
                continue
            text = turn.get("text")
            if isinstance(text, str):
                if text.strip() == "Question [number].":
                    turn["text"] = f"Question {idx}."
                elif text.strip() == "[question_text]" and question_text is not None:
                    turn["text"] = str(question_text)
        fixed_items.append(item)
    part_data["items"] = fixed_items
    return part_data


def pick_unused_reading_file(
    *,
    reading_short_dir: Path,
    reading_long_dir: Path,
    repo_root: Optional[Path] = None,
    record_path: Optional[Path] = None,
    rng: Optional[random.Random] = None,
    allow_all_if_exhausted: bool = False,
    mark_used: bool = True,
) -> Path:
    """
    Reading_Short / Reading_Long から「未使用のみ」をランダム選択して返す。
    - 未使用が尽きた場合は allow_all_if_exhausted で挙動を切替。
    """
    if rng is None:
        rng = random.Random()
    if repo_root is None:
        repo_root = _find_repo_root()
    if record_path is None:
        record_path = _default_used_reading_record_path(repo_root)

    candidates = _reading_file_candidates(
        reading_short_dir=reading_short_dir,
        reading_long_dir=reading_long_dir,
    )
    if not candidates:
        raise ValueError("No reading candidate .txt files found.")

    used_relpaths = _read_used_reading_record(record_path)

    available: list[Path] = []
    for p in candidates:
        rel = str(p.relative_to(repo_root))
        if rel not in used_relpaths:
            available.append(p)

    if not available:
        if not allow_all_if_exhausted:
            raise ValueError(
                f"All reading candidate files are marked used. record={record_path} "
                f"(candidates={len(candidates)})"
            )
        available = candidates

    chosen = rng.choice(available)
    rel_chosen = str(chosen.relative_to(repo_root))
    if mark_used:
        used_relpaths.add(rel_chosen)
        _write_used_reading_record(record_path, used_relpaths=sorted(used_relpaths))
    return chosen
