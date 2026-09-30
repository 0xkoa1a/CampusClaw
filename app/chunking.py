"""Lossless source-positioned chunks and a small Chinese-friendly keyword index."""

import re
from collections import Counter
from dataclasses import dataclass


BOUNDARIES = ("\n\n", "\n", "。")
TOKEN_RE = re.compile(r"[\u3400-\u9fff]+|[a-zA-Z0-9_]+")
HEADING_RE = re.compile(r"(?m)^#{1,6} +(.+)$")


@dataclass(frozen=True)
class Chunk:
    body: str
    start_offset: int
    end_offset: int
    heading: str = ""


def validate_strategy(strategy):
    strategy = strategy or {}
    if not isinstance(strategy, dict):
        raise ValueError("切分策略必须是对象")
    kind = strategy.get("type", "auto")
    if kind not in {"auto", "delimiter", "markdown"}:
        raise ValueError("不支持的切分策略")
    size = strategy.get("max_chars", 800)
    overlap = strategy.get("overlap", 80)
    if type(size) is not int or not 100 <= size <= 2000:
        raise ValueError("max_chars 必须在 100–2000 之间")
    if type(overlap) is not int or not 0 <= overlap <= size // 2:
        raise ValueError("overlap 必须在 0 到 max_chars 的 50% 之间")
    delimiter = strategy.get("delimiter", "")
    if kind == "delimiter" and (not isinstance(delimiter, str) or not delimiter):
        raise ValueError("自定义切分需要非空 delimiter")
    return {"type": kind, "max_chars": size, "overlap": overlap, "delimiter": delimiter}


def _windows(text, begin, end, size, overlap, heading=""):
    position = begin
    while position < end:
        stop = min(position + size, end)
        if stop < end:
            for marker in BOUNDARIES:
                match = text.rfind(marker, position + size // 2, stop)
                if match >= 0:
                    stop = match + len(marker)
                    break
        if text[position:stop].strip():
            yield Chunk(text[position:stop], position, stop, heading)
        if stop == end:
            break
        position = max(position + 1, stop - overlap)


def split_text(text, strategy=None):
    options = validate_strategy(strategy)
    size, overlap = options["max_chars"], options["overlap"]
    kind = options["type"]
    if kind == "auto":
        return list(_windows(text, 0, len(text), size, overlap))
    if kind == "delimiter":
        result = []
        begin = 0
        delimiter = options["delimiter"]
        while begin < len(text):
            found = text.find(delimiter, begin)
            end = len(text) if found < 0 else found + len(delimiter)
            result.extend(_windows(text, begin, end, size, overlap))
            begin = end
        return result
    headings = list(HEADING_RE.finditer(text))
    if not headings:
        return list(_windows(text, 0, len(text), size, overlap))
    result = []
    if headings[0].start():
        result.extend(_windows(text, 0, headings[0].start(), size, overlap))
    path = []
    for index, match in enumerate(headings):
        depth = len(match.group().split(" ", 1)[0])
        path = path[: depth - 1]
        path.append(match.group(1).strip())
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        result.extend(_windows(text, match.start(), end, size, overlap, " / ".join(path)))
    return result


def terms(text):
    result = Counter()
    for match in TOKEN_RE.finditer(text.casefold()):
        token = match.group()
        if "\u3400" <= token[0] <= "\u9fff":
            if len(token) == 1:
                result[token] += 1
            else:
                result.update(token[index : index + 2] for index in range(len(token) - 1))
        else:
            result[token] += 1
    return result
