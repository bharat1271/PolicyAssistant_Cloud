"""
config.py
────────────────────────────────────────────────────────────────────────────────
Single place for every tunable value in the project — same philosophy as the
local version's config.py: keep the "what" (paths, model names, thresholds)
separate from the "how" (parsing, chunking, ranking).

THIS IS THE CLOUD VERSION. It's a separate project folder from
PolicyAssistant_Portfolio (the local/Ollama version), not a mode-switch inside
the same codebase. Three things had to change to survive Streamlit Community
Cloud, and this file is where two of the three live:

  1. LLM: Ollama (local server) -> Groq API (hosted). GROQ_API_KEY below.
  2. Embeddings: nomic-embed-text via Ollama -> sentence-transformers
     (all-MiniLM-L6-v2), which runs in-process on CPU. No local server needed,
     no API key needed for this part — the model weights download once from
     Hugging Face and are cached.
  3. Vector store: ChromaDB's persistent client -> nothing, because there's
     nothing to persist. At ~25 chunks, the whole index fits in memory and
     gets rebuilt at app startup (see app.py's @st.cache_resource). This
     swap lives in retrieval.py, not here — see that file's docstring for
     why ChromaDB specifically doesn't work well on Streamlit Cloud.

Everything else (chunk size, RRF constant, chapters, noise pattern, system
prompt) is identical to the local version, because none of that logic is
backend-specific.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Source document ───────────────────────────────────────────────────────────
DOCX_PATH = BASE_DIR / "data" / "MasterDataGovernancePolicy.docx"

# ── Groq API key ──────────────────────────────────────────────────────────────
# Resolution order: environment variable first (useful for local testing via
# `export GROQ_API_KEY=...`), then Streamlit secrets (how it's supplied once
# deployed to Streamlit Community Cloud — see README.md for the exact steps).
# Never hardcode the key itself in this file.
def _get_groq_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return ""

GROQ_API_KEY = _get_groq_api_key()

# ── Models ─────────────────────────────────────────────────────────────────────
# Groq-hosted LLM. gpt-oss-20b is a good default: fast, cheap, strong enough
# for grounded Q&A over a few retrieved chunks. Swap to llama-3.3-70b-versatile
# if answer quality needs to go up and latency/cost can flex.
LLM_MODEL = "openai/gpt-oss-20b"

# sentence-transformers embedding model. all-MiniLM-L6-v2 is the standard
# lightweight default (384-dim, ~80MB) — small enough to load quickly on
# Streamlit Cloud's shared CPU resources, no GPU required.
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── Chunking ───────────────────────────────────────────────────────────────────
# Same values as the local version — chunking is a document-structure decision,
# not a backend decision, so it doesn't change across versions.
CHUNK_SIZE    = 700
CHUNK_OVERLAP = 120

# ── Retrieval ──────────────────────────────────────────────────────────────────
TOP_N                  = 8     # chunks returned to the LLM per query
RRF_K                  = 60    # standard Reciprocal Rank Fusion constant
SIMILARITY_THRESHOLD   = 0.80  # cosine distance cutoff; 0 = identical, 2 = opposite
MAX_KEYWORDS           = 4     # cap on keyword-search terms extracted per question
MAX_CHUNKS_PER_SECTION = 2     # diversity cap so one section can't dominate context

# Section headers that mark the start of a new top-level chapter (as opposed to
# a sub-heading within the current chapter).
CHAPTERS = {
    "EntityNames",
    "EntityAddresses",
    "EntityType",
    "Determining EntityLevel for Organizations",
    "Guidelines for RelTypes",
    "Variants",
    "Process for Deprecating Entities",
    "Multi-Location Organizations",
    "Change Log",
}

# Bold lines that LOOK like section headers (short + bold) but are actually
# metadata or navigation.
NOISE_PATTERN = (
    r'^(Updated|Version|Date[:\s]|Owners?[:\s]|Added |Note[:\s]|Go back|'
    r'V \d+\.|Target Audience|Purpose$|Concepts$|\(Go back)'
)

# ── LLM system prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a policy assistant for the Enterprise Data Governance Team.
Answer using only the policy context provided below.
If the answer is not in the context, say so and suggest checking the full \
document or a data steward.

Policy Context:
{context}"""
