# Policy Assistant — Cloud Version (Streamlit Community Cloud + Groq)

Same product as [`PolicyAssistant_Portfolio`](../PolicyAssistant_Portfolio) —
a hybrid-RAG chat assistant grounded in a structured policy document — rebuilt
to run as a public, hosted Streamlit app instead of on a local machine with
Ollama. Same synthetic policy document, same retrieval logic, same UI. Three
backend swaps, described below.

If you haven't read the local version's README yet, read that one first — it
explains *why* the retrieval design (structure-aware parsing, hybrid
semantic+keyword search, RRF fusion, section diversity capping) looks the way
it does. This README only covers what's different here and why.

---

## Why a separate folder instead of one codebase with a mode switch

An earlier iteration of this project tried to keep local and cloud in one
codebase behind a config flag, with the embedding/LLM/vector-store calls
factored into their own shared modules (`embeddings.py`, `llm.py`,
`vectorstore.py`). That added a layer of indirection — you had to open two or
three files to see what actually happens for one backend — before there was
any real payoff from sharing code, since the local and cloud paths only share
about a dozen lines of logic (chunking, RRF, section-diversity) in the first
place. Two small, fully-readable, single-purpose folders turned out to be
easier to explain and easier to maintain than one clever one.

## The three things that had to change, and why each one specifically breaks on Streamlit Cloud

It's tempting to assume "deploying to the cloud" just means swapping the LLM
from local to API-based. That's necessary but not sufficient here — three
separate pieces of the stack assumed a local machine, not one.

**1. LLM — Ollama → Groq API**
Ollama is a server process (`ollama serve`) that has to be running on the same
machine as the app. Streamlit Community Cloud has no such server available,
and there's no way to install and run one inside a hosted app's environment.
Groq is a hosted API reachable over HTTPS from anywhere, so the app just needs
an API key, not a co-located server. `config.py` resolves `GROQ_API_KEY` from
an environment variable first, falling back to Streamlit's `st.secrets`
mechanism — the key itself is never hardcoded or committed. Model:
`openai/gpt-oss-20b`, a fast/cheap Groq-hosted model that's strong enough for
grounded Q&A over a handful of retrieved chunks (`llama-3.3-70b-versatile` is
a reasonable step up if answer quality needs to improve).

**2. Embeddings — Ollama's nomic-embed-text → sentence-transformers, in-process**
Same root cause as #1: `ollama.embeddings(...)` also needs the local Ollama
server. The fix here is different from the LLM fix, though — instead of
calling another hosted API, embeddings are generated in-process with
`sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions, ~80MB). The model
weights download once from Hugging Face and then run directly on CPU inside
the Streamlit app's own process. No server, no second API key, no added
network dependency at query time.

**3. Vector store — ChromaDB persistent client → in-memory numpy array**
This is the swap that's easiest to miss if you assume "cloud = swap the LLM."
Two independent problems with carrying ChromaDB's `PersistentClient` over to
Streamlit Cloud: (a) a Streamlit Cloud app's filesystem is rebuilt on
redeploy, so an on-disk "persistent" index isn't reliably persistent in that
environment anyway; (b) ChromaDB depends on a newer SQLite version than what
Streamlit Cloud's base image ships — a known, documented compatibility
failure. Given the actual corpus size here (~25 chunks), the fix is simpler
than working around either problem: build the whole chunk list and its
embedding matrix once at app startup (`@st.cache_resource` in `app.py`,
replacing the local version's one-time `python ingest.py` step), and do exact
brute-force cosine similarity with numpy at query time (`doc_vecs @
query_vector`, since every embedding is L2-normalized so the dot product IS
the cosine similarity). No FAISS, no approximate-nearest-neighbor index —
those exist to make search fast at a scale (millions of vectors) this project
doesn't operate at. Using FAISS here would be complexity added for a problem
that doesn't exist yet; the retrieval logic itself (`retrieval.py`) is
otherwise identical to the local version's RRF + section-diversity approach.

## What did NOT change

- `docx_parser.py` and `chunker.py` are byte-for-byte copies of the local
  version's files. Structure-aware parsing and character-based chunking have
  nothing to do with where the LLM or vector index live.
- `generate_synthetic_policy.py` is also an unchanged copy — same synthetic
  document, so the two versions are directly comparable side by side.
- The retrieval *logic* (RRF merge, section-diversity cap, keyword extraction)
  is unchanged, only the storage/search *mechanism* underneath it is different
  — see `retrieval.py`'s docstring for the line-by-line diff explanation.
- The system prompt, chunk size (700/120), and every retrieval threshold are
  identical to the local version.

## Architecture

```
data/MasterDataGovernancePolicy.docx
        │  (generated once via generate_synthetic_policy.py)
        ▼
docx_parser.py  — bold headers = section boundaries, tables → pipe-delimited text
        ▼
chunker.py      — 700-char chunks, 120-char overlap
        ▼
app.py `_build_index()` — @st.cache_resource, runs once per app lifetime:
                  embeds every chunk (sentence-transformers, CPU, in-process),
                  keeps {chunks, doc_vecs} in memory — no ingest.py, no on-disk DB
        │
        │  ◄── at query time ──►
        ▼
retrieval.py    — hybrid_retrieve():
                    1. semantic search: numpy cosine similarity over doc_vecs
                    2. keyword search: case-insensitive substring scan
                    3. RRF merge (k=60)
                    4. section-diversity cap (max 2 chunks/section)
        ▼
app.py          — Streamlit chat UI, streams the Groq LLM response
                  (openai/gpt-oss-20b), shows which policy sections were
                  retrieved for each answer
```

## Project layout

| File | Responsibility |
|---|---|
| `config.py` | Every tunable value: Groq key resolution, model names, chunk/retrieval settings |
| `docx_parser.py` | Structure-aware document parsing — unchanged copy from the local version |
| `chunker.py` | Overlap-aware text splitting — unchanged copy from the local version |
| `generate_synthetic_policy.py` | Builds the sample policy `.docx` — unchanged copy |
| `retrieval.py` | Hybrid RRF retrieval, rewritten for an in-memory numpy index instead of ChromaDB |
| `app.py` | Streamlit chat UI — builds the index at startup, embeds/generates inline (no separate embeddings.py/llm.py), streams answers |

Note there's no `ingest.py` in this version — with no persistent database to
populate ahead of time, `app.py`'s cached `_build_index()` function does that
job at startup instead.

---

## Setup: local test run (do this before deploying)

Always test locally first — cheaper and faster to debug an API key or import
error on your own machine than through a Streamlit Cloud redeploy cycle.

```bash
cd PolicyAssistant_Cloud
pip install -r requirements.txt

# Get a free Groq API key at https://console.groq.com/keys
export GROQ_API_KEY=your_key_here        # macOS/Linux
# set GROQ_API_KEY=your_key_here         # Windows cmd
# $env:GROQ_API_KEY="your_key_here"      # Windows PowerShell

python generate_synthetic_policy.py      # builds data/MasterDataGovernancePolicy.docx
streamlit run app.py
```

The first run will take a little longer than usual — sentence-transformers
downloads and caches the `all-MiniLM-L6-v2` model weights the first time it's
used. Subsequent runs are fast.

If you'd rather not use an environment variable locally, create
`.streamlit/secrets.toml` in this folder:

```toml
GROQ_API_KEY = "your_key_here"
```

(`.gitignore` already excludes this file so the key is never committed.)

## Setup: deploying to Streamlit Community Cloud

1. **Push this folder to GitHub.** It needs to be its own repo, or at least
   its own subfolder in a repo — Streamlit Cloud deploys from a specific file
   path in a specific repo/branch. Make sure `data/MasterDataGovernancePolicy.docx`
   is committed (run `generate_synthetic_policy.py` and commit the output, or
   have Streamlit Cloud generate it — see step 4).

2. **Go to** [share.streamlit.io](https://share.streamlit.io) **and sign in**
   with GitHub.

3. **Click "New app"**, then select:
   - Repository: the repo you pushed in step 1
   - Branch: `main` (or whichever branch has this code)
   - Main file path: `PolicyAssistant_Cloud/app.py` (adjust if this folder
     isn't at the repo root)

4. **Before or after the first deploy, add your secret.** In the app's
   settings (⋮ menu → Settings → Secrets), add:
   ```toml
   GROQ_API_KEY = "your_key_here"
   ```
   This is what `config.py`'s `_get_groq_api_key()` falls back to reading via
   `st.secrets` when there's no environment variable set (there won't be one
   in this hosted environment).

5. **Deploy.** Streamlit Cloud installs `requirements.txt` and runs the app.
   The first load will be slower than normal while sentence-transformers
   downloads its model weights — that's expected and only happens once per
   redeploy (the cache persists across user sessions, not across redeploys).

6. **Get your public link** from the app's page (`https://<something>.streamlit.app`)
   — this is what goes on LinkedIn/resume.

## Example questions to try

Same as the local version — the retrieval design is the same, so the same
questions exercise the same edge cases:

- "What does EntityLevel 3 mean?"
- "What are all the approved RelType values?" (tests enumeration coverage)
- "Who owns this policy?" (tests the semantic-near-miss handling)
- "How do I handle an entity with no known city?"
- "What's the process for deprecating an entity?"

## Interview talking points, condensed

- Cloud deployment isn't "swap the LLM" — three things assumed a local
  machine (LLM, embedding model, vector store), and each broke for a
  different, specific reason on Streamlit Cloud (no Ollama server; same
  reason for embeddings; ChromaDB's SQLite version requirement / non-durable
  filesystem for the vector store).
- Why numpy instead of FAISS: at this corpus size (~25 chunks), brute-force
  cosine similarity is already sub-millisecond. FAISS solves a scale problem
  (millions of vectors) this project doesn't have — using it here would be
  unjustified complexity, not correctness.
- Why two separate project folders instead of one pluggable codebase: the
  amount of logic actually shared between local and cloud (chunking, RRF,
  section-diversity) is small relative to the amount that differs, so a
  config-flag abstraction added indirection without much payoff.
- Why `app.py` inlines the embed/generate calls instead of factoring them into
  `embeddings.py`/`llm.py`: at this project's size, one file you can read
  top-to-bottom beats three files you have to cross-reference.

## What I'd change with more time

- Add a lightweight disk cache for the embedding matrix (e.g. pickle it after
  first build) so a redeploy doesn't always re-embed from scratch — marginal
  here at 25 chunks, but the right move if the document grows.
- Add an eval set of question/expected-section pairs to track retrieval
  quality numerically instead of by spot-checking answers (same item as the
  local version's README — still true here).
- Swap substring keyword matching for true BM25 scoring (`rank_bm25`) if the
  document grows large enough that literal substring search starts missing
  morphological variants.
