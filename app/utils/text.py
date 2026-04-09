from __future__ import annotations


def truncate_for_whatsapp(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 1].rstrip()
    # Try not to cut mid-word if possible.
    last_space = clipped.rfind(" ")
    if last_space > max_chars * 0.7:
        clipped = clipped[:last_space].rstrip()
    return clipped + "…"

