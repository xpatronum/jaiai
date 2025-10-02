import re
from typing import List, Tuple

import json_repair

# ---------- Хелперы парсинга markdown с восстановлением JSON ----------
TOPICS_RE = re.compile(r"(?im)^\s*topics\s*:\s*(\[[^\]]*\])\s*$", re.MULTILINE)
SENTS_RE = re.compile(r"(?im)^\s*sentiments\s*:\s*(\[[^\]]*\])\s*$", re.MULTILINE)
VALID_SENT = {"положительно", "отрицательно", "нейтрально"}


def _maybe_fix_json_list(s: str) -> List[str]:
    """
    Чиним кривой JSON от модели (одинарные кавычки, висячие запятые и т.п.)
    и грузим через json_repair.loads(...)
    """
    s = s.strip()
    try:
        out = json_repair.loads(s)
        if isinstance(out, list):
            return [str(x).strip() for x in out]
    except Exception:
        pass
    # last resort: пусто
    return []


def _extract_md_pairs(markdown: str) -> Tuple[List[str], List[str]]:
    topics_m = TOPICS_RE.search(markdown or "")
    sents_m = SENTS_RE.search(markdown or "")
    topics = _maybe_fix_json_list(topics_m.group(1)) if topics_m else []
    sentiments = [
        x.lower() for x in (_maybe_fix_json_list(sents_m.group(1)) if sents_m else [])
    ]
    # валидация
    if len(topics) != len(sentiments):
        return [], []
    if any(s not in VALID_SENT for s in sentiments):
        return [], []
    return topics, sentiments


__all__ = ["_extract_md_pairs"]
