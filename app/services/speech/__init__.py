"""Speech synthesis (Azure)."""

from app.services.speech.azure_speech import (
    _split_config,
    passage_signature,
    split_listening_script,
    synthesize_script_to_bytes,
)

__all__ = [
    "_split_config",
    "passage_signature",
    "split_listening_script",
    "synthesize_script_to_bytes",
]
