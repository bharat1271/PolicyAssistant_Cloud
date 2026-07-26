"""
chunker.py
────────────────────────────────────────────────────────────────────────────────
Splits a section's text into embedding-sized chunks.

WHY A CUSTOM CHUNKER INSTEAD OF A LIBRARY SPLITTER
Early iterations of this project used LangChain's RecursiveCharacterTextSplitter.
It works, but pulling in LangChain as a dependency just for text splitting also
pulls in its versioning churn everywhere else in the stack. This ~30-line
function does the same job — break on paragraph, then sentence, then word
boundaries, with overlap — without the dependency.

A NOTE ON THE LOOP TERMINATION CONDITION
The `if end >= len(text): break` at the bottom is not decorative. An earlier
version of this function was missing it: on the final chunk of a section,
`start = end - overlap` could produce a `start` that never reaches `len(text)`
if `end` stayed pinned at `len(text)` every iteration — an infinite loop that
only showed up on certain section lengths. This is a good example of why
chunking logic deserves a unit test (see the __main__ block below) rather than
"looks right, ship it."
"""


def split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Greedily fills chunks up to `chunk_size` characters, then backs off to the
    nearest paragraph/sentence/word boundary so we don't cut a sentence in
    half. Each chunk overlaps the previous one by `overlap` characters so a
    rule that happens to fall right on a chunk boundary is still fully
    readable in at least one chunk.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    # Guarantees each chunk is at least (chunk_size - overlap) characters, so
    # the boundary search below always has room to look backward without
    # collapsing into a zero-length or negative-length chunk.
    min_advance = chunk_size - overlap

    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Prefer a paragraph break, then a line break, then sentence end,
            # then a plain space — in that priority order.
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, start + min_advance, end)
                if idx != -1:
                    end = idx + len(sep)
                    break

        piece = text[start:end].strip()
        if len(piece) > 15:  # skip near-empty fragments
            chunks.append(piece)

        if end >= len(text):
            break
        start = end - overlap

    return chunks


if __name__ == "__main__":
    # Sanity checks — run `python chunker.py` directly.
    sample = ("Sentence one. " * 5) + ("\n\n" + "Sentence two. " * 40)

    chunks = split_into_chunks(sample, chunk_size=100, overlap=20)
    print(f"{len(sample)} chars -> {len(chunks)} chunks")
    for i, c in enumerate(chunks):
        print(f"  chunk {i}: {len(c)} chars")

    # Regression test for the infinite-loop bug described above.
    edge_case = "x" * 701  # one char longer than CHUNK_SIZE
    result = split_into_chunks(edge_case, chunk_size=700, overlap=120)
    assert len(result) >= 1, "chunker should terminate and return at least one chunk"
    print("Edge-case (infinite loop regression) test passed.")
