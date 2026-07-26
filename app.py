"""
app.py
────────────────────────────────────────────────────────────────────────────────
Streamlit chat UI for the Policy Assistant — CLOUD version.

This is the Streamlit Community Cloud-deployable sibling of
PolicyAssistant_Portfolio/app.py. Same product (chat with a structured policy
document, grounded answers, section citations), different backend, and this
file is deliberately NOT split into embeddings.py / llm.py / vectorstore.py —
every embed call and every generate call is written inline, right where it's
used, so the whole request path reads top-to-bottom in one file.

WHAT CHANGED FROM THE LOCAL VERSION, AND WHY (three swaps, not one)

  1. LLM: `ollama.chat(...)` -> Groq's `client.chat.completions.create(...)`.
     Streamlit Community Cloud has no Ollama server to talk to — Ollama is a
     process you run on your own machine. Groq is a hosted API, reachable
     from anywhere, authenticated with GROQ_API_KEY (see config.py).

  2. Embeddings: `ollama.embeddings(...)` -> a `SentenceTransformer` model
     loaded in-process. Same reason as above — no Ollama server on Streamlit
     Cloud. sentence-transformers ships the model weights via Hugging Face
     and runs it directly in the Python process on CPU, so no server or API
     key is needed for this half of the pipeline.

  3. Vector store: `chromadb.PersistentClient(...)` -> a plain Python list of
     chunk dicts plus a numpy matrix of their embeddings, both built once at
     startup and cached with `@st.cache_resource`. Two independent reasons
     ChromaDB's persistent client doesn't carry over cleanly to Streamlit
     Cloud: (a) Streamlit Cloud's filesystem for an app is ephemeral / rebuilt
     on redeploy, so a "persisted" on-disk index isn't reliably persistent
     there anyway, and (b) ChromaDB depends on a SQLite version newer than
     what Streamlit Cloud's base image ships, a known compatibility issue.
     Rebuilding an in-memory index at startup sidesteps both problems, and at
     ~25 chunks the rebuild takes well under a second.

Run locally (for testing before deploying):
    streamlit run app.py
Requires GROQ_API_KEY set as an environment variable or in .streamlit/secrets.toml
(see README.md for both local testing and full Streamlit Cloud deployment steps).
"""

import time
from datetime import datetime

import numpy as np
import streamlit as st
from docx import Document
from groq import Groq
from sentence_transformers import SentenceTransformer

from config import (
    DOCX_PATH, GROQ_API_KEY, LLM_MODEL, EMBED_MODEL,
    CHUNK_SIZE, CHUNK_OVERLAP, SYSTEM_PROMPT, TOP_N,
)
from docx_parser import extract_sections
from chunker import split_into_chunks
from retrieval import hybrid_retrieve

st.set_page_config(page_title="Policy Assistant", page_icon="📋", layout="centered")


@st.cache_resource(show_spinner="Loading and indexing policy document...")
def _build_index():
    """
    Runs once per app lifetime (Streamlit caches the return value across all
    users' sessions, not just one). This replaces the local version's
    one-time `python ingest.py` step — there's no separate ingest script here
    because there's no database to populate ahead of time; the whole index
    is small enough to build on the fly at startup instead.

    Returns:
        chunks:   list of {"text", "chapter", "section"} dicts
        doc_vecs: numpy array (num_chunks, embed_dim), L2-normalized so a dot
                  product with a query vector equals cosine similarity
        embedder: the loaded SentenceTransformer, reused for embedding queries
    """
    if not DOCX_PATH.exists():
        return None, None, None

    doc = Document(str(DOCX_PATH))
    sections = extract_sections(doc)

    chunks = []
    for s in sections:
        for piece in split_into_chunks(s["text"], CHUNK_SIZE, CHUNK_OVERLAP):
            chunks.append({"text": piece, "chapter": s["chapter"], "section": s["section"]})

    embedder = SentenceTransformer(EMBED_MODEL)
    texts = [c["text"] for c in chunks]
    doc_vecs = embedder.encode(texts, normalize_embeddings=True)
    doc_vecs = np.asarray(doc_vecs)

    return chunks, doc_vecs, embedder


def _format_chat_for_download(messages: list) -> str:
    lines = [
        "Policy Assistant — Chat Export",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60, "",
    ]
    for msg in messages:
        role = "You" if msg["role"] == "user" else "Policy Assistant"
        lines.append(f"[{role}]")
        lines.append(msg["content"])
        if msg.get("sources"):
            lines.append("")
            lines.append("  Sections retrieved:")
            for src in msg["sources"]:
                lines.append(f"  - {src['section']} — {src['chapter']}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("")
    return "\n".join(lines)


def main():
    st.title("📋 Policy Assistant")
    st.caption(
        "Ask questions about the Master Entity Data Governance Policy. "
        "Hybrid retrieval (semantic + keyword, RRF-merged) + Groq-hosted LLM — "
        "cloud-deployable version, see README.md for what changed vs. the local build."
    )

    if not GROQ_API_KEY:
        st.error(
            "No GROQ_API_KEY found. Set it as an environment variable, or in "
            "`.streamlit/secrets.toml` locally, or in the app's Secrets panel "
            "on Streamlit Community Cloud. See README.md."
        )
        return

    chunks, doc_vecs, embedder = _build_index()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Index status")
        if chunks is not None:
            st.success(f"{len(chunks)} chunks indexed (in-memory)")
        else:
            st.error(f"Source document not found at {DOCX_PATH.name}")
        st.divider()
        st.markdown("### How it works")
        st.write("1. Document parsed by section/table structure (`docx_parser.py`)")
        st.write("2. Chunked with overlap (`chunker.py`)")
        st.write("3. Embedded in-process (sentence-transformers) and kept in memory")
        st.write("4. Hybrid semantic + keyword retrieval, RRF-merged (`retrieval.py`)")
        st.write("5. Answered by Groq-hosted LLM, grounded strictly in retrieved context")
        st.divider()
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        if st.session_state.messages:
            st.download_button(
                "Download chat",
                data=_format_chat_for_download(st.session_state.messages).encode("utf-8"),
                file_name="policy_chat.txt",
                mime="text/plain",
                use_container_width=True,
            )

    if chunks is None:
        st.warning(f"Place the source document at data/{DOCX_PATH.name}, or run "
                   "`python generate_synthetic_policy.py`, then refresh this page.")
        return

    # ── Chat history ─────────────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("time"):
                st.caption(f"{msg['time']}s")
            if msg.get("sources"):
                with st.expander("Policy sections retrieved"):
                    for src in msg["sources"]:
                        st.caption(f"{src['section']} — {src['chapter']}")
                        st.write(src["text"])
                        st.divider()

    user_input = st.chat_input("Ask about the policy...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Searching policy..."):
            query_vector = embedder.encode(user_input, normalize_embeddings=True)
            query_vector = np.asarray(query_vector)
            docs, metas = hybrid_retrieve(chunks, doc_vecs, query_vector, user_input, n=TOP_N)
            context = "\n\n---\n\n".join(docs)

            chat_messages = [{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}]
            for m in st.session_state.messages[-6:-1]:
                chat_messages.append({"role": m["role"], "content": m["content"]})
            chat_messages.append({"role": "user", "content": user_input})

        client = Groq(api_key=GROQ_API_KEY)
        start = time.time()
        stream = client.chat.completions.create(
            model=LLM_MODEL,
            messages=chat_messages,
            temperature=0.1,
            stream=True,
        )

        def _token_stream():
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        answer = st.write_stream(_token_stream())
        elapsed = time.time() - start
        st.caption(f"{elapsed:.1f}s")

        sources = [
            {"section": m.get("section", ""), "chapter": m.get("chapter", ""), "text": d}
            for d, m in zip(docs, metas)
        ]
        with st.expander("Policy sections retrieved"):
            for src in sources:
                st.caption(f"{src['section']} — {src['chapter']}")
                st.write(src["text"])
                st.divider()

    st.session_state.messages.append({
        "role": "assistant", "content": answer, "sources": sources, "time": round(elapsed, 1),
    })


if __name__ == "__main__":
    main()
