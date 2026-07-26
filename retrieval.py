"""
retrieval.py
────────────────────────────────────────────────────────────────────────────────
Hybrid retrieval: semantic vector search + keyword search, merged with
Reciprocal Rank Fusion (RRF), then filtered for section diversity.

This is the SAME retrieval logic as the local version (PolicyAssistant_Portfolio
/retrieval.py) — same two failure modes it's designed around (semantic
near-miss on "owner" vs "owned", enumeration under-coverage on the RelType
table), same RRF math, same section-diversity cap. Read that file's docstring
for the full reasoning; it isn't repeated here.

WHAT'S DIFFERENT IN THIS CLOUD VERSION, AND WHY
The local version calls `collection.query(...)` on a live ChromaDB collection,
because ChromaDB is doing the vector search and the substring search for you.
This version has no database at all — at ~25 chunks, the entire corpus fits
in memory as a plain Python list, so both searches are just a few lines of
Python instead of a query language:

  - Semantic search: every chunk's embedding is a numpy row in a matrix built
    once at startup (see app.py). Cosine similarity against the query vector
    is one matrix-vector multiply (`doc_vecs @ query_vec`, since embeddings
    are pre-normalized to unit length, dot product = cosine similarity).
    No ANN index (e.g. FAISS) is used, deliberately — an approximate-nearest-
    neighbor structure exists to make search on millions of vectors fast;
    at 25 vectors an exact brute-force scan is already sub-millisecond, so
    FAISS would be complexity with no payoff here.
  - Keyword search: a plain `keyword.lower() in chunk_text.lower()` substring
    check. The local version tries three casing variants per keyword because
    ChromaDB's `$contains` filter is case-sensitive; scanning a Python list
    directly means one `.lower()` call handles every case variant at once —
    no database-level quirk to work around.

Everything downstream of "how do I get a ranked list of candidate chunks" —
the RRF merge and the section-diversity cap — is untouched, because that
logic was never about ChromaDB in the first place.
"""

import numpy as np

from config import RRF_K, SIMILARITY_THRESHOLD, MAX_KEYWORDS, MAX_CHUNKS_PER_SECTION

_STOPWORDS = {
    "what", "is", "are", "the", "a", "an", "how", "do", "does", "can",
    "when", "why", "who", "which", "this", "that", "was", "were", "be",
    "been", "have", "has", "had", "will", "would", "could", "should",
    "may", "might", "about", "for", "of", "in", "to", "and", "or", "but",
    "if", "on", "with", "as", "at", "by", "me", "my", "you", "your",
    "give", "tell", "explain", "list", "show", "find", "get", "any",
    "difference", "between", "different", "there", "it", "its",
}


def _extract_keywords(query_text: str) -> list[str]:
    """Strip stopwords and short tokens, keeping only words likely to be
    meaningful search terms (entity-domain nouns, table column values, etc.).
    Identical to the local version — keyword extraction has nothing to do
    with where the chunks are stored."""
    return [
        w.strip("?.,!()")
        for w in query_text.split()
        if w.strip("?.,!()").lower() not in _STOPWORDS and len(w.strip("?.,!()")) > 3
    ]


def hybrid_retrieve(chunks: list[dict], doc_vecs: np.ndarray, query_vector: np.ndarray,
                     query_text: str, n: int = 8):
    """
    Returns (docs, metas) — up to `n` chunk texts and their {chapter, section}
    metadata, ranked by combined semantic + keyword relevance and capped for
    section diversity.

    Args:
        chunks:       list of {"text", "chapter", "section"} dicts, one per
                      chunk, built once at startup (see app.py).
        doc_vecs:     numpy array, shape (num_chunks, embed_dim), row i is the
                      normalized embedding of chunks[i]["text"]. Built once at
                      startup alongside `chunks`, in the same order.
        query_vector: normalized embedding of the current question, same
                      dimensionality as doc_vecs's rows.
        query_text:   the raw question text, used for keyword extraction.
        n:            how many chunks to return.
    """
    keywords = _extract_keywords(query_text)[:MAX_KEYWORDS]

    rrf_scores: dict[int, float] = {}   # chunk index -> cumulative RRF score

    # ── 1. Semantic search ────────────────────────────────────────────────────
    # Both doc_vecs rows and query_vector are unit-normalized (see app.py), so
    # a plain dot product IS cosine similarity — no separate normalization
    # step needed here.
    similarities = doc_vecs @ query_vector
    distances = 1 - similarities  # convert to the same "distance" scale the
                                   # local version's ChromaDB cosine space uses,
                                   # so SIMILARITY_THRESHOLD means the same thing
                                   # in both versions.
    ranked_by_similarity = np.argsort(distances)  # ascending distance = best first

    for rank, idx in enumerate(ranked_by_similarity[:n]):
        if distances[idx] < SIMILARITY_THRESHOLD:
            rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (RRF_K + rank + 1)

    # ── 2. Keyword search ─────────────────────────────────────────────────────
    # A single case-insensitive substring check per chunk. No casing-variant
    # loop needed (unlike the local version's ChromaDB $contains workaround) —
    # .lower() on both sides handles every case in one comparison.
    for kw in keywords:
        kw_lower = kw.lower()
        for idx, chunk in enumerate(chunks):
            if kw_lower in chunk["text"].lower():
                rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (RRF_K + 0 + 1)

    # ── 3. Merge by combined RRF score ────────────────────────────────────────
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # ── 4. Section diversity cap ──────────────────────────────────────────────
    section_count: dict[str, int] = {}
    final_docs, final_metas = [], []
    for idx, _ in ranked:
        chunk = chunks[idx]
        section = chunk.get("section", "")
        if section_count.get(section, 0) < MAX_CHUNKS_PER_SECTION:
            final_docs.append(chunk["text"])
            final_metas.append({"chapter": chunk.get("chapter", ""), "section": section})
            section_count[section] = section_count.get(section, 0) + 1
        if len(final_docs) >= n:
            break

    return final_docs, final_metas
