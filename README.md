# Policy Assistant

A RAG (Retrieval-Augmented Generation) chat assistant that answers natural-language questions about a structured policy document, with every answer grounded in the actual retrieved text and citing which section it came from.

This is the cloud-hosted version, deployed on Streamlit Community Cloud with Groq for generation. There's also a fully local version of this same project that runs offline with Ollama, no API key or internet needed. See `../PolicyAssistant_Portfolio`.

**Live demo: streamlit.app](https://policyassistantcloud.streamlit.app/

## Why I built this

Most "chat with your document" demos just dump a file into a generic text splitter and call it a day. That throws away the one thing a structured document like a policy manual actually gives you for free: its own structure. A rule and the table underneath it belong together. A chunk should know which chapter it came from, so an answer can point back to it.

I built this to work through that problem properly: parsing by document structure instead of raw character count, and using hybrid retrieval (not just vector search) to fix two specific failure modes that pure semantic search runs into on this kind of document.

A note on the source document: this project mirrors the structure of a real internal policy document I built a version of at work (chapters, sub-sections, embedded rule tables). The document here is a synthetic one I wrote myself for this portfolio version. Same retrieval challenges, zero real company data.

## What it does

You ask a question in plain English, like "what are all the approved RelType values" or "who owns this policy." The assistant retrieves the most relevant chunks of the policy document, shows you exactly which sections it pulled from, and answers using only that retrieved context. If the answer isn't in the document, it says so instead of guessing.

## The two retrieval problems this is designed around

Plain vector (cosine similarity) search fails in two specific, reproducible ways on a rules-heavy policy document:

**Semantic near-miss.** A question like "who is the owner of this policy?" embeds close to content about "Jointly-Owned-By" relationships, because "owner" and "owned" sit close together in embedding space, even though the user is asking about document stewardship, not an entity relationship type. Vector search alone returns the wrong chunk with high confidence.

**Enumeration under-coverage.** A question like "what are all the RelTypes?" has nine correct answers sitting in one table. Vector search's top-k can return five of nine and rank the rest below unrelated-but-semantically-close chunks. The model then has no way of knowing its context is incomplete.

Keyword search (plain substring match) fixes both. A literal "owner" search finds the metadata line regardless of embedding distance, and a literal "RelType" search surfaces every chunk that mentions it. I merge the two ranked lists with Reciprocal Rank Fusion (RRF) rather than just concatenating them, since cosine distance and a substring match aren't on a comparable scale, and rank position is the one thing both search types can be compared on fairly.

On top of that, I cap how many chunks can come from the same section, so one dominant topic (like the RelType table) can't crowd out every other section the answer might also need.

## Tech stack

- Streamlit for the chat UI
- Groq (`openai/gpt-oss-20b`) for the LLM, called via the Groq Python SDK
- sentence-transformers (`all-MiniLM-L6-v2`) for embeddings, run in-process on CPU
- numpy for cosine similarity search over the chunk embeddings
- python-docx for parsing the source Word document

No vector database. At this document's size (about 25 chunks), a plain in-memory list plus a numpy matrix is simpler and just as fast as standing up a database for it. More on that below.

## Architecture

```
data/MasterDataGovernancePolicy.docx
        |
        v
docx_parser.py   bold paragraphs = section headers, tables flattened to text
        |
        v
chunker.py       700-char chunks, 120-char overlap, breaks on sentence/paragraph bounds
        |
        v
app.py           builds the index once at startup (cached):
                 embeds every chunk with sentence-transformers, keeps
                 {chunks, embeddings} in memory
        |
        |  <-- at query time -->
        v
retrieval.py     hybrid_retrieve():
                   1. semantic search: cosine similarity via numpy
                   2. keyword search: case-insensitive substring scan
                   3. merge by Reciprocal Rank Fusion (k=60)
                   4. cap chunks per section for topic diversity
        |
        v
app.py           streams the Groq response, shows which sections it used
```

## Project layout

| File | What it does |
|---|---|
| `config.py` | every tunable value in one place: API key handling, model names, chunk size, retrieval thresholds |
| `docx_parser.py` | walks the Word document in order, splits it into chapter/section/text blocks |
| `chunker.py` | splits each section's text into overlapping, embedding-sized chunks |
| `generate_synthetic_policy.py` | builds the sample policy document used in this repo |
| `retrieval.py` | hybrid search: semantic + keyword, merged with RRF, capped for section diversity |
| `app.py` | the Streamlit app: builds the index at startup, handles chat, calls Groq |

## How embeddings and search work here

An embedding is just a list of numbers that represents the meaning of a piece of text. Two chunks of text that mean similar things end up with numbers that are close together. That's what makes "search by meaning" possible instead of just exact keyword matching.

Every chunk of the policy document gets turned into one of these number-vectors when the app starts up, using a small pretrained model (`all-MiniLM-L6-v2`) that runs directly inside the app, no external server needed. Those vectors are kept in memory for the lifetime of the app rather than saved to a database, since 25 chunks is small enough that rebuilding the index at startup takes a fraction of a second.

When you ask a question, it gets turned into the same kind of vector, and I compare it against every chunk's vector with a single matrix multiplication (`numpy`), which is what "cosine similarity search" reduces to once every vector is normalized to the same length. No approximate-nearest-neighbor index (like FAISS) is involved, on purpose. Those exist to make search fast across millions of vectors. At this scale, that's solving a problem I don't have.

## Setup: run it locally

```bash
git clone <your-repo-url>
cd PolicyAssistant_Cloud
pip install -r requirements.txt

python generate_synthetic_policy.py
```

Then set your Groq API key (get a free one at [console.groq.com/keys](https://console.groq.com/keys)) using one of these two methods:

**Option A, environment variable:**
```bash
export GROQ_API_KEY=your_key_here        # macOS/Linux
setx GROQ_API_KEY "your_key_here"        # Windows
```

**Option B, local secrets file:** create `.streamlit/secrets.toml` in this folder:
```toml
GROQ_API_KEY = "your_key_here"
```
This file is already excluded in `.gitignore`, so it never gets committed.

Then run:
```bash
streamlit run app.py
```

The first run downloads the embedding model weights (about 80MB), so it'll take a little longer than usual. After that it's fast.

## Setup: deploy your own copy to Streamlit Community Cloud

1. Push this folder to a GitHub repo. Make sure `data/MasterDataGovernancePolicy.docx` is committed.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click "New app," pick the repo and branch, and set the main file path to `app.py` (or `PolicyAssistant_Cloud/app.py` if this folder isn't at the repo root).
4. Before or after the first deploy, open the app's settings and add your key under the "Secrets" tab:
   ```toml
   GROQ_API_KEY = "your_key_here"
   ```
5. Deploy. First load is slower while the embedding model downloads; that only happens once per redeploy.
6. Grab the public `*.streamlit.app` link from the app page.

## Example questions to try

- "What does EntityLevel 3 mean?"
- "What are all the approved RelType values?"
- "Who owns this policy?"
- "How do I handle an entity with no known city?"
- "What's the process for deprecating an entity?"

## Design decisions

**Why RRF instead of just picking whichever search scored higher?** Cosine similarity and substring match aren't on a comparable numeric scale, so they can't be added together meaningfully. Rank position is the one thing both search types produce comparably.

**Why numpy instead of FAISS?** FAISS solves the problem of searching millions of vectors quickly. This project has about 25. Brute-force cosine similarity over that many vectors is already sub-millisecond, so adding an approximate-nearest-neighbor library would be complexity with no real benefit.

**Why one `app.py` instead of separate files for embeddings, retrieval, and generation?** I split out `retrieval.py` because that logic is substantial and genuinely reusable. But the actual embed and generate calls are just a couple of lines each, so I kept them inline in `app.py` rather than adding files that would mostly just forward a call to a library.

**Why Streamlit secrets instead of a `.env` file?** Streamlit Community Cloud doesn't read `.env` files at all, since the app's filesystem comes fresh from the GitHub repo on every deploy and a `.env` file is (correctly) never committed. Streamlit's own secrets manager exists specifically to solve this: it stores the key outside of git, injects it at runtime, and works the same way locally (via `.streamlit/secrets.toml`) and in the cloud (via the app's Secrets tab). `config.py` reads an environment variable first and falls back to `st.secrets`, so both approaches work without needing a second dependency like `python-dotenv`.

## What I'd change with more time

- Cache the embedding matrix to disk so a redeploy doesn't re-embed every chunk from scratch. Not worth it yet at 25 chunks, but the right move if the document grows.
- Replace substring keyword matching with real BM25 scoring (`rank_bm25`) for a larger, more varied document.
- Add an eval set of question and expected-section pairs, to measure retrieval quality instead of spot-checking answers.
