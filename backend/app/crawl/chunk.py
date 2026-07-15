"""Split extracted page text into overlapping chunks for embedding."""

CHUNK_CHARS = 1000       # ~ matches the internal documents' chunk size
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 60     # drop tiny fragments (nav crumbs etc.)


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Chunk on paragraph boundaries where possible, packing up to ~`size` chars with overlap."""
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paras:
        if len(buf) + len(para) + 1 <= size:
            buf = f"{buf}\n{para}".strip()
            continue
        if buf:
            chunks.append(buf)
        # start next buffer with a tail overlap of the previous chunk for context continuity
        buf = (buf[-overlap:] + "\n" + para).strip() if buf and overlap else para
        # a single very long paragraph: hard-split it
        while len(buf) > size:
            chunks.append(buf[:size])
            buf = buf[size - overlap:]
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]
