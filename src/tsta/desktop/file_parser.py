"""Parse common uploaded files into plain text for use as knowledge base.

Supported: text (.txt/.md/.csv/.json/.py/.log/...), PDF, Word (.docx),
Excel (.xlsx). Parsers are imported lazily so the optional deps only load
when a matching file is actually parsed.
"""

from __future__ import annotations

from pathlib import Path

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".py", ".log",
    ".ini", ".yaml", ".yml", ".xml", ".html", ".htm", ".c", ".cpp", ".h",
    ".java", ".js", ".ts", ".sh", ".bat", ".sql", ".rst",
}


def parse_file(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".pdf":
        return _parse_pdf(p)
    if ext == ".docx":
        return _parse_docx(p)
    if ext in {".xlsx", ".xlsm"}:
        return _parse_xlsx(p)
    return _parse_text(p)


def _parse_text(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_pdf(p: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(p))
    parts = []
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — skip unreadable pages
            text = ""
        if text.strip():
            parts.append(f"[第 {i} 页]\n{text.strip()}")
    return "\n\n".join(parts)


def _parse_docx(p: Path) -> str:
    # Read word/document.xml directly via zipfile — extracts all paragraph/table
    # text WITHOUT touching embedded images (which can be corrupt and raise
    # "Bad CRC-32" when python-docx loads the full package).
    import zipfile
    from xml.etree import ElementTree

    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(str(p)) as z:
        xml = z.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    lines = []
    for para in root.iter(W + "p"):
        text = "".join((t.text or "") for t in para.iter(W + "t"))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def _parse_xlsx(p: Path) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(str(p), read_only=True, data_only=True)
    try:
        parts = []
        for ws in wb.worksheets:
            parts.append(f"[工作表: {ws.title}]")
            for row in ws.iter_rows(values_only=True):
                if any(c is not None for c in row):
                    parts.append("\t".join("" if c is None else str(c) for c in row))
        return "\n".join(parts)
    finally:
        wb.close()
