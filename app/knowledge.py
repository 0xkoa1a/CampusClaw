def parse_text(raw):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("文件必须是 UTF-8 文本") from exc
    if not text.strip():
        raise ValueError("文件不能为空")
    return text
