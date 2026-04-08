"""
Azure Speech Service: listening script を音声合成し bytes で返す.
設定未設定時は None を返し、呼び出し側でスキップする.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings

logger = logging.getLogger(__name__)


DEFAULT_VOICE_MAP: Dict[str, Dict[str, str]] = {
    "narrator": {"name": "en-US-DavisNeural", "rate": "0.9", "pitch": "+7.5%", "style": "general"},
    "man": {"name": "en-US-GuyNeural", "rate": "1.0", "pitch": "+0.0%", "style": "friendly"},
    "woman": {"name": "en-US-JennyNeural", "rate": "1.0", "pitch": "+3.5%", "style": "chat"},
}


@lru_cache(maxsize=1)
def _load_speech_config() -> Dict[str, Any]:
    """speech_config.yaml を読み込み、無ければ空 dict."""
    try:
        import yaml
    except ImportError:
        return {}
    base = Path(__file__).resolve().parent
    for _ in range(3):
        base = base.parent
    config_path = base / "speech_config.yaml"
    if not config_path.is_file():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _get_voice_map() -> Dict[str, Dict[str, str]]:
    cfg = _load_speech_config()
    voices = cfg.get("voices")
    if isinstance(voices, dict) and voices:
        normalized: Dict[str, Dict[str, str]] = {}
        for key, v in voices.items():
            if isinstance(v, dict):
                name = str(v.get("name") or DEFAULT_VOICE_MAP.get(key, {}).get("name") or "").strip()
                rate = str(v.get("rate") or DEFAULT_VOICE_MAP.get(key, {}).get("rate") or "1.0").strip()
                pitch = str(v.get("pitch") or DEFAULT_VOICE_MAP.get(key, {}).get("pitch") or "0%").strip()
                style = str(v.get("style") or DEFAULT_VOICE_MAP.get(key, {}).get("style") or "").strip()
                if name:
                    normalized[key] = {"name": name, "rate": rate, "pitch": pitch, "style": style}
        if normalized:
            return normalized
    return DEFAULT_VOICE_MAP


def _get_break_rules() -> Dict[str, Any]:
    cfg = _load_speech_config()
    rules = cfg.get("break_rules")
    if isinstance(rules, dict):
        return rules
    return {}


def _split_config() -> Dict[str, Any]:
    """speech_config の split / passage / question 設定を返す."""
    cfg = _load_speech_config()
    return {
        "split_passage_questions": bool(cfg.get("split_passage_questions")),
        "deduplicate_passage_blocks": bool(cfg.get("deduplicate_passage_blocks")),
        "passage_speakers": list(cfg.get("passage_speakers") or ["man", "woman"]),
        "question_speaker": str(cfg.get("question_speaker") or "narrator").lower(),
        "question_turn_rule": str(cfg.get("question_turn_rule") or "last_narrator"),
    }


def split_listening_script(script: List[Dict[str, Any]]) -> tuple:
    """
    listening_script を (本文用 script, 設問用 script) に分割する.
    戻り値: (passage_script, question_script). いずれも List[Dict].
    """
    cfg = _split_config()
    passage_speakers = {s.lower() for s in cfg["passage_speakers"]}
    question_speaker = cfg["question_speaker"]
    rule = cfg["question_turn_rule"]

    passage_script = [
        t for t in script
        if (t.get("speaker") or "").lower() in passage_speakers
        or (t.get("speaker") or "").lower() == "break"
    ]
    narrator_turns = [t for t in script if (t.get("speaker") or "").lower() == question_speaker]
    if rule == "last_narrator" and narrator_turns:
        question_script = [narrator_turns[-1]]
    else:
        question_script = list(narrator_turns)

    return (passage_script, question_script)


def passage_signature(script: List[Dict[str, Any]]) -> str:
    """本文部分の同一性判定用文字列. ブロック検出に使う."""
    passage_script, _ = split_listening_script(script)
    return json.dumps(passage_script, sort_keys=True, ensure_ascii=False)


def _build_ssml(script: List[Dict[str, Any]]) -> str:
    """listening_script 形式 [{"speaker": "man", "text": "..."}] から SSML を組み立てる."""
    parts = [
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">'
    ]
    voice_map = _get_voice_map()
    break_rules = _get_break_rules()
    on_question_contains = str(break_rules.get("on_question_contains") or "Question")
    narrator_question_break = str(break_rules.get("narrator_question_break") or "1500ms")
    speaker_breaks = break_rules.get("speaker_breaks") or {}
    default_speaker_break = str(speaker_breaks.get("default") or "1000ms")
    default_break_seconds = float(break_rules.get("break_speaker_default_seconds") or 10.0)
    for turn in script:
        speaker = (turn.get("speaker") or "narrator").lower()
        text = turn.get("text") or ""

        if speaker == "break":
            try:
                sec = float(str(text).strip() or str(default_break_seconds))
            except ValueError:
                sec = default_break_seconds
            name = voice_map["narrator"]["name"]
            parts.append(f'<voice name="{name}"><break time="{sec}s" /></voice>')
            continue

        voice = voice_map.get(speaker, voice_map["narrator"])
        parts.append(f'<voice name="{voice["name"]}">')
        if voice.get("style"):
            parts.append(f'<mstts:express-as style="{voice["style"]}">')
        parts.append(f'<prosody rate="{voice["rate"]}" pitch="{voice["pitch"]}">')
        parts.append(text)
        parts.append("</prosody>")
        if voice.get("style"):
            parts.append("</mstts:express-as>")
        if speaker == "narrator" and on_question_contains in text:
            parts.append(f'<break time="{narrator_question_break}" />')
        else:
            speaker_break = str(speaker_breaks.get(speaker) or default_speaker_break)
            parts.append(f'<break time="{speaker_break}" />')
        parts.append("</voice>")
    parts.append("</speak>")
    return "".join(parts)


def synthesize_script_to_bytes(script: List[Dict[str, Any]]) -> bytes:
    """
    listening_script ([{"speaker": "man"|"woman"|"narrator"|"break", "text": "..."}]) を
    Azure Speech で合成し、音声 bytes (WAV) を返す.
    失敗時は ValueError を送出する.
    """
    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        logger.warning("azure-cognitiveservices-speech がインストールされていません")
        raise ValueError(
            "Azure Speech SDK が未導入です: azure-cognitiveservices-speech をインストールしてください"
        )

    settings = get_settings()
    if not settings.azure_speech_key or not settings.azure_speech_region:
        logger.debug("Azure Speech 未設定 (AZURE_SPEECH_KEY / AZURE_SPEECH_REGION)")
        raise ValueError(
            "Azure Speech 設定が不足しています: AZURE_SPEECH_KEY / AZURE_SPEECH_REGION を設定してください"
        )

    endpoint = f"https://{settings.azure_speech_region}.api.cognitive.microsoft.com/"
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.azure_speech_key,
        endpoint=endpoint,
    )

    cfg = _load_speech_config()
    fmt_name = str(cfg.get("output_format") or "Riff24Khz16BitMonoPcm")
    output_format = getattr(
        speechsdk.SpeechSynthesisOutputFormat,
        fmt_name,
        speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm,
    )
    speech_config.set_speech_synthesis_output_format(output_format)

    # メモリに出力するため audio_config=None
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    ssml = _build_ssml(script)
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            error_details = getattr(details, "error_details", details)
            logger.error("Azure Speech キャンセル: %s", error_details)
            raise ValueError(f"Azure Speech キャンセル: {error_details}")
        else:
            logger.error("Azure Speech 失敗: %s", result.reason)
            raise ValueError(f"Azure Speech 合成失敗: reason={result.reason}")

    stream = speechsdk.AudioDataStream(result)
    chunks = []
    # Azure SDK が要求する型が `bytes` のため、bytearray を渡すと ValueError になる
    # (audio_buffer must be a bytes)
    buf = bytes(32000)
    while True:
        n = stream.read_data(buf)
        if n <= 0:
            break
        chunks.append(bytes(buf[:n]))
    return b"".join(chunks)
