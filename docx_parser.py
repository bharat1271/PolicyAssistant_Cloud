"""
docx_parser.py
────────────────────────────────────────────────────────────────────────────────
Turns a structured Word document into a flat list of (chapter, section, text)
blocks, in document order.

WHY A CUSTOM PARSER INSTEAD OF A GENERIC LOADER
A generic PDF/docx loader (e.g. langchain's PyPDFLoader) treats a document as
one long stream of text and chunks it purely by character count. That throws
away the document's own structure — which, for a policy document, IS the most
useful retrieval signal you have: a rule and the table underneath it belong
together, and a chunk should know which chapter/section it came from so a
user question like "what does Level 3 mean?" can be traced back to the
"Determining EntityLevel for Organizations" chapter specifically.

This parser exploits one convention that's common in real-world policy docs:
section headers are bold, short paragraphs. Everything else (body text,
tables) is content that belongs to whichever header came before it.

HOW TO READ THIS FILE
1. iter_body()          — walk paragraphs and tables in the order they appear
                           in the file (python-docx does not do this for you
                           by default — paragraphs and tables are two separate
                           lists that lose their interleaving).
2. is_section_header()  — decide if a paragraph is a real header or a
                           bold-but-not-a-header line (see NOISE_PATTERN below).
3. table_to_text()      — flatten a Word table into plain text so it can be
                           embedded like any other chunk.
4. extract_sections()   — the main loop: walk the document, and every time a
                           new header appears, close out the previous section
                           and start a new one.
"""

import re
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table

from config import CHAPTERS, NOISE_PATTERN

_NOISE = re.compile(NOISE_PATTERN, re.IGNORECASE)


def iter_body(doc: Document):
    """
    Yield ('para', Paragraph) or ('table', Table) for every element in the
    document body, IN ORDER. python-docx exposes doc.paragraphs and
    doc.tables as two separate lists — walking doc.element.body directly is
    what lets us reconstruct the original interleaving (a paragraph, then a
    table, then more paragraphs, etc.).
    """
    for child in doc.element.body:
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            yield 'para', Paragraph(child, doc)
        elif tag == 'tbl':
            yield 'table', Table(child, doc)


def is_bold(para: Paragraph) -> bool:
    """A paragraph counts as bold if any non-empty run in it is bold. Word
    stores formatting per-run, not per-paragraph, so a paragraph can have a
    mix of bold and non-bold runs — we treat it as bold if any part is."""
    return any(run.bold for run in para.runs if run.text.strip())


def is_section_header(para: Paragraph) -> bool:
    """
    A real section header is: bold, short, and not a metadata/navigation line.

    The length cutoff (90 chars) exists because inline bold emphasis inside a
    long sentence ("...must **never** be left blank...") would otherwise be
    misread as a header. Real headers in practice are short phrases.

    The NOISE_PATTERN exclusion exists because "Owner:", "Version:", "Date:",
    "Go back to Table of Contents" etc. are ALSO bold and short, but they are
    metadata/navigation, not content boundaries. Without this filter, every
    "Owner:" line would incorrectly start a brand-new (nearly empty) section.
    """
    t = para.text.strip()
    if not t or not is_bold(para):
        return False
    if len(t) > 90:
        return False
    if _NOISE.match(t):
        return False
    return True


def table_to_text(tbl: Table) -> str:
    """
    Flatten a Word table into pipe-delimited text rows, e.g.:
        RelType | Definition
        Parent-Of | Entity A directly controls Entity B

    Word repeats a merged cell's text in every cell it spans — the dedup step
    below collapses consecutive duplicate cells in a row so a merged header
    cell doesn't appear three times in the flattened text.
    """
    rows = []
    for row in tbl.rows:
        cells = [c.text.strip().replace('\n', ' ') for c in row.cells]
        deduped = []
        for c in cells:
            if not deduped or c != deduped[-1]:
                deduped.append(c)
        rows.append(' | '.join(deduped))
    return '\n'.join(r for r in rows if r.strip())


def extract_sections(doc: Document) -> list[dict]:
    """
    Walk the document body in order and group content into
    {chapter, section, text} blocks.

    - "chapter"  = the top-level heading this content falls under
                   (e.g. "Guidelines for RelTypes")
    - "section"  = the specific sub-heading within that chapter, if any
                   (defaults to the chapter name itself if there is no
                   finer-grained sub-heading)
    - "text"     = every paragraph and table that appeared between this
                   header and the next one

    Each new section's first line is tagged "[Section: <name>]" so that even
    after the text is later split into smaller chunks, every chunk still
    carries its own section label as embedded context — this is what lets the
    LLM's answer cite "which section" it came from.
    """
    sections: list[dict] = []
    current_chapter = "General"
    current_section = "General"
    buffer: list[str] = []

    def flush():
        text = '\n'.join(buffer).strip()
        # 20-char floor keeps genuinely empty sections out, but still keeps
        # short-but-real content blocks (a one-line rule, a short note).
        if text and len(text) > 20:
            sections.append({
                "chapter": current_chapter,
                "section": current_section,
                "text": text,
            })
        buffer.clear()

    for kind, obj in iter_body(doc):
        if kind == 'para':
            t = obj.text.strip()
            if not t:
                continue

            if is_section_header(obj):
                flush()
                if t in CHAPTERS:
                    current_chapter = t
                    current_section = t
                else:
                    current_section = t
                buffer.append(f"[Section: {t}]")
            else:
                buffer.append(t)

        elif kind == 'table':
            ttext = table_to_text(obj)
            if ttext.strip():
                buffer.append(f"[Table]\n{ttext}")

    flush()
    return sections


if __name__ == "__main__":
    # Quick manual check: run `python docx_parser.py` to see how the current
    # document gets sliced up, without needing Ollama/ChromaDB running.
    from config import DOCX_PATH

    doc = Document(str(DOCX_PATH))
    sections = extract_sections(doc)
    print(f"{len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables in source doc")
    print(f"{len(sections)} sections extracted\n")
    for s in sections:
        preview = s["text"].replace("\n", " ")[:70]
        print(f"[{s['chapter']:<45}] {s['section']:<40} | {preview}...")
