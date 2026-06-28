# Code Walkthrough — Foras Khadra Smart Search


Demo Video: https://youtu.be/HuCsCaxyoRI

This document walks through every file I wrote, what it does, and why I made the decisions I made instead of other options.

---

## Project Structure

```
Foras3/
├── backend/
│   ├── main.py           # FastAPI app, /search and /chat endpoints, session store
│   ├── chatbot.py        # Groq LLM integration, manages conversation history
│   ├── searcher.py       # Full pipeline: normalize, expand, embed, score, rank, highlight
│   ├── embedder.py       # SentenceTransformer wrapper with query/passage prefixing
│   ├── data_loader.py    # Loads data, manages embedding cache, builds tag index
│   ├── enrich_tags.py    # One-time script to generate bilingual tags via LLM
│   └── test_search.py    # Pytest tests for normalization and search quality
├── data/
│   ├── opportunities.json    # Mock opportunities with enriched tags
│   └── embeddings.pkl        # Auto-generated on first run, not committed to git
├── frontend/
│   ├── index.html        # Main page, RTL layout
│   ├── search.js         # Search logic, card rendering, skeleton loading states
│   ├── chat.js           # Chat popup, session ID management
│   └── style.css         # All styles
└── README.md
```

---

## How to Run

Clone the repo then setup the backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn sentence-transformers groq python-dotenv numpy pytest
```

Create a `.env` file in the root of the project:

```
GROQ_API_KEY=your_key_here
```

Start the server:

```bash
uvicorn main:app --reload
```

First run will take around 20 to 30 seconds because the embedding model need to download and compute embeddings for all opportunities. After that the cache kicks in and every restart is fast.

Then open `frontend/index.html` directly in your browser, no build step needed.

To run tests:

```bash
pytest test_search.py -v
```

---

## embedder.py

This is the lowest level piece and everything else depends on it so I'll start here.

```python
MODEL_NAME = "intfloat/multilingual-e5-large"
model = SentenceTransformer(MODEL_NAME)
```

The model loads once at module import time. I did it this way deliberately so there is no lazy loading surprise on the first request. The server takes a bit longer to start but every request after that is fast.

Why `intfloat/multilingual-e5-large` specifically and not something like `paraphrase-multilingual-mpnet-base-v2` or any other multilingual model? Two reasons. First, e5 is trained with explicit query/passage distinction which is exactly the retrieval use case I have — the query and the documents are treated differently in the embedding space, which gives better results than treating them the same way. Second, the "large" variant scores meaningfully better on Arabic retrieval benchmarks than the base size, and since the embeddings are computed once and cached the inference cost at search time is just one query embedding which is fast regardless of model size.

```python
def embed_queries(texts, batch_size=64):
    prefixed = ["query: " + t for t in texts]
    return model.encode(prefixed, normalize_embeddings=True, batch_size=batch_size)

def embed_passages(texts, batch_size=64):
    prefixed = ["passage: " + t for t in texts]
    return model.encode(prefixed, normalize_embeddings=True, batch_size=batch_size)
```

The `query:` and `passage:` prefixes are not optional with e5, they are part of how the model was trained. If you skip them the similarity scores degrade noticeably. I split this into two functions instead of one function with a parameter because calling the wrong one is a hard-to-debug bug, and having two clearly named functions makes that impossible to mess up accidentally.

`normalize_embeddings=True` means the vectors come out with unit length, which lets me use dot product instead of full cosine similarity. With unit vectors, dot product and cosine similarity are mathematically identical but dot product is faster.

---

## data_loader.py

This file handles two things: loading opportunities with embedding cache management, and building the inverted tag index.

**The cache logic:**

```python
def hash_json(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()
```

The cache stores the MD5 hash of the JSON file alongside the embeddings. On every startup it checks if the hash matches. If the data file changed or if the model name changed, it recomputes. If not, it loads from disk. This was important to add because computing embeddings for all opportunities with the large model takes 20-30 seconds and nobody wants to wait for that on every server restart.

Why pickle for the cache and not something like numpy's `.npy` format? Because I'm storing a dict that contains the hash string, model name string, and the numpy array all together. Pickle handles heterogeneous Python objects easily. If I used `.npy` I'd have to store the metadata separately in a second file and keep them in sync, which is more complexity for no real benefit at this scale.

**The tag index:**

```python
def build_tag_index(opportunities):
    index = {}
    for opp in opportunities:
        for tag in opp.get("tags", []):
            tag_clean = tag.lower().strip()
            if len(tag_clean) >= 3:
                index.setdefault(tag_clean, [])
                if opp_id not in index[tag_clean]:
                    index[tag_clean].append(opp_id)
        combined = " ".join(text_sources).lower()
        words = set(re.findall(r'\w+', combined))
        for word in words:
            if len(word) >= 3:
                ...
```

This builds a dictionary mapping every term to a list of opportunity IDs that contain it. The 3-character minimum filters out noise like "of", "in", "to" without needing a stopword list. I index both the full tag phrases AND individual words from title, organization, and location because users search both ways, they might type the full program name "chevening scholarship" or just "chevening" or just "scholarship".

Why build this at startup instead of querying it at search time with a database? Because the data fits entirely in memory and a Python dict lookup is O(1). A database query for every search request would be slower and adds infrastructure dependency I don't need.

---

## enrich_tags.py

This is a one-time script, not part of the server. I run it once to enrich the data, it writes back to the JSON, and then I commit the enriched data.

The prompt I wrote for tag generation is doing a lot of work:

```
Generate 12-18 search tags for the opportunity below.
RULES:
- Include program name and common aliases/abbreviations
- Include country name in BOTH English and Arabic
- Include field/topic in BOTH languages
- Include organisation name and abbreviation
- Include opportunity type in both languages
- Include target audience
- Include funding info if applicable
- ALL tags must be lowercase
- NO duplicates
```

Why generate tags with an LLM instead of just extracting keywords from the description? Because the descriptions are in English but users search in Arabic. A keyword extractor would give me English keywords only. I need bilingual coverage and semantic variations, not just "scholarship" but also "منحة" and "grant" and "fellowship". The LLM can generate all of these from a single English description and that is something no keyword extractor can do.

I use temperature 0.2 here, lower than the chatbot. Tags need to be factual and consistent, I don't want the model being creative about what country a scholarship is from.

The exponential backoff on retries (`time.sleep(2 ** attempt)`) is there because the Groq free tier has rate limits. If a batch job hits the rate limit the backoff gives the API time to recover before retrying. I chose Groq here because it is the free option available to me, the API is simple to integrate and fast enough for a one-time enrichment script. It is not the best LLM for this kind of structured generation task but it gets the job done and for generating tags Claude or GPT-4 would give cleaner output honestly.

---

## searcher.py

This is the most complex file. The full search pipeline lives here.

**Arabic normalization:**

```python
ARABIC_CORRECTIONS = {
    "الاصتناعي": "الاصطناعي",
    "منحه": "منحة",
    "وضيفة": "وظيفة",
    ...
}

def normalise_arabic(text):
    # 1. fix known typos
    words = text.split()
    corrected = [ARABIC_CORRECTIONS.get(w, w) for w in words]
    text = " ".join(corrected)
    # 2. strip diacritics
    text = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', text)
    # 3. normalize alef forms
    text = re.sub(r'[أإآ]', 'ا', text)
    # 4. normalize ya and waw
    text = re.sub(r'ى', 'ي', text)
    ...
```

Why do this manually instead of using a library like camel-tools or pyarabic? Because I want full control and minimal dependencies. The normalization I need is not that complex, fix the specific typos users actually make, strip diacritics, normalize alef forms. camel-tools is a heavy dependency for what would amount to three regex substitutions and a lookup dict. I also built the typo dictionary from actual common mistakes rather than a generic one which means it is tuned to this domain specifically.

**Synonym expansion:**

```python
SYNONYMS = {
    "بريطانيا": ["uk", "united", "kingdom", "britain", "england"],
    "منحة": ["scholarship", "grant", "fellowship", "award"],
    "تدريب": ["internship", "training", "intern"],
    ...
}
```

This is the part that bridges Arabic queries to English data. Without this, semantic similarity alone handles meaning reasonably well but exact keyword matching falls apart completely for cross-language queries. The expanded terms feed into the keyword boost, so a user who types "بريطانيا" gets a boost on results that contain "uk" or "united kingdom" in their tags even if the semantic score alone did not surface them at the top.

I built this dictionary manually rather than using a translation API because I want predictable domain-specific expansions. A translation API might translate "منحة" to just "grant" and miss "scholarship" and "fellowship" which are the actual terms used in the data.

**Scoring:**

```python
final_scores = np.array([
    semantic_scores[i] + keyword_boost(query, active[i])
    for i in range(len(active))
])
```

Final score is semantic cosine similarity plus keyword boost. The boost is capped by the `boost` parameter (0.08 by default) and scaled by the ratio of query words that matched, so it can never dominate over the semantic score, it just nudges results that also have keyword matches. This hybrid approach beats either method alone — pure semantic search misses exact program name matches, pure keyword search misses meaning entirely.

**Highlight extraction:**

```python
def extract_highlights_batch(query_emb, opportunities):
    all_sentences = []
    for opp in opportunities:
        sentences = opp["description"].split(".")
        all_sentences.extend(sentences)
    all_embs = embed_passages(all_sentences, batch_size=64)
    scores = cosine_sim(query_emb, all_embs)[0]
    # pick best sentence per opportunity
    ...
```

Why batch the sentence embeddings instead of processing one opportunity at a time? Because the sentence transformer is much more efficient embedding 200 sentences at once than 5 sentences at a time for 40 opportunities. GPU and CPU utilization is better, and the batch_size=64 parameter lets the model pack sentences efficiently. The first version of this was a loop per opportunity and it was noticeably slower.

---

## main.py

The FastAPI app. This file is mostly glue, it wires the other modules together and handles HTTP.

**Startup:**

```python
all_opportunities, all_embeddings = load_opportunities()
active_opportunities, active_embeddings = filter_expired_with_embeddings(...)
tag_index = build_tag_index(active_opportunities)
embed_queries(["warmup"])
```

I filter expired opportunities at startup and keep both the filtered list and the sliced embedding matrix in sync. Why do this at startup instead of filtering per request? Because if I filter at query time I have to do it on every request which means comparing dates on every single search. Doing it once at startup means every search operates on already-clean data.

The warmup call `embed_queries(["warmup"])` forces the model to process one query before the server starts accepting traffic. Without this the first real request takes a few seconds longer because the model is lazy about allocating GPU memory. This makes the first user experience consistent with every request after it.

**Session management:**

```python
session_store: dict[str, list] = defaultdict(list)
SESSION_MAX_TURNS = 20
```

Sessions are just a Python dict in memory. Each session ID maps to the conversation history. The 20-turn limit trims old messages to avoid hitting token limits. This is intentionally simple, for a production system you would use Redis or a database but for this use case an in-memory store is fine.

Why `defaultdict(list)` instead of a regular dict? Because accessing a new session ID automatically creates an empty list without needing an `if session_id not in session_store` check. Small thing but it makes the route handler cleaner.

**The `/search` endpoint uses `run_in_threadpool`:**

```python
return await run_in_threadpool(
    search, body.query, active_opportunities, active_embeddings, top_k, False
)
```

The search function is CPU-bound, numpy operations and model inference. FastAPI is async but CPU-bound work blocks the event loop if you just await it directly. `run_in_threadpool` offloads it to a thread pool so the event loop stays free to handle other requests while the search is running. Same pattern for the chat route.

---

## chatbot.py

```python
def chat(history, opportunities=None, active_embeddings=None, tag_index=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.5,
        max_tokens=800
    )
```

The function signature accepts `opportunities`, `active_embeddings`, and `tag_index` as parameters even though they are not used yet. I put them there intentionally as the interface for the next version where the chatbot will have the actual search results injected as context. Right now the model answers from general knowledge about these programs which is the main limitation of the chatbot currently. The fix is to serialize the relevant opportunity cards into the system prompt before the user question and the signature is already set up for that.

Temperature 0.5 is a middle ground, lower than creative tasks and higher than the tag generation script. The chatbot needs to be helpful and natural in tone but should not be making up specific details about deadlines or requirements.

Why Groq with llama-3.3-70b and not OpenAI or Claude API? Simply because Groq is free. For a task submission I needed something I can actually run without paying and Groq gave me that. llama-3.3-70b handles Arabic reasonably well but I will be honest, Claude or GPT-4 would give noticeably better answers especially on nuanced questions in Arabic. The good thing is the integration pattern is identical regardless of which provider you swap in, just change the client and the model name.

---

## test_search.py

```python
def test_germany_scholarship():
    titles = top_titles("منحة في المانيا", n=3)
    assert any("داد" in t or "المانيا" in t or "DAAD" in t for t in titles)

def test_ai_internship_typo():
    titles = top_titles("تدريب في الاصتناعي", n=3)
    assert any("ذكاء" in t or "AI" in t or "تعلم" in t for t in titles)
```

I wrote two categories of tests. Normalization unit tests that check specific string transformations in isolation, and search quality tests that check whether real queries return reasonable results. The quality tests are the more important ones because they test the full pipeline end to end and not just individual functions in isolation.

The typo test specifically (`test_ai_internship_typo`) is testing the normalization and search pipeline together, it verifies that "الاصتناعي" which is missing the ط still returns AI-related results after normalization kicks in.

I did not mock the model in the search quality tests. Some people would argue you should mock for speed but for search quality tests you actually need the real model because the whole point is to test whether the semantic similarity scores are sensible, mocking that defeats the purpose.

---

## frontend — index.html

Plain HTML with no framework. I chose this because the frontend is simple enough that React or Vue would add build toolchain complexity for zero benefit. The whole UI is one page with two tabs and a persistent chat popup, that does not justify a framework.

RTL is handled at the `<html>` level with `dir="rtl"` and `lang="ar"` which means the browser handles text direction natively without needing CSS workarounds per element.

---

## frontend — search.js

```javascript
async function doSearch() {
    showSkeleton();
    const res = await fetch(`${API}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 15 }),
    });
    const data = await res.json();
    currentData = data.results;
    renderCards(currentData, { expired_filtered: data.expired_filtered });
    if (typeof initChatWithResults === "function") {
        initChatWithResults(currentData);
    }
}
```

`showSkeleton()` renders placeholder card shapes before the API call resolves. This gives the user immediate visual feedback that something is happening instead of staring at a frozen UI. The skeleton uses a CSS shimmer animation.

`currentData` is a module-level variable that holds the last search results. The filter chips operate on this local copy without making another API call which makes filtering instant. The live search bar also filters `currentData` locally.

The `initChatWithResults` call at the end is what triggers the chat popup after every search. I use `typeof` check instead of calling it directly so the files can be loaded in either order without breaking.

---

## frontend — chat.js

```javascript
async function sendPopupChat() {
    const res = await fetch(`${API_CHAT}/chat`, {
        method: "POST",
        body: JSON.stringify({
            session_id: sessionId,  // null on first message
            message: message
        }),
    });
    const data = await res.json();
    sessionId = data.session_id;
}
```

`sessionId` starts as null. The first message goes to the backend without a session ID, the backend creates one and returns it, and from that point every subsequent message includes the session ID so the backend can retrieve the conversation history. This way the frontend does not need to manage history at all, it just tracks the ID and the backend handles the rest.

The popup is built dynamically with `buildChatPopup()` and `buildLauncher()` instead of being in the HTML from the start. This is because the chat popup only makes sense after a search, there are no results to talk about otherwise. `initChatWithResults()` in search.js calls these functions so the popup does not exist in the DOM at all until the first search completes.

---

## data/opportunities.json

Mock data where each opportunity has `id`, `title`, `title_ar`, `type`, `organisation`, `location`, `description`, `deadline`, `link`, and `tags` fields. The tags field starts minimal and gets enriched by `enrich_tags.py`. The description field is what gets embedded so it needs to be rich enough for the semantic search to work well, a two-word description would give poor results.

---

## How everything connects at request time

User types query → `search.js doSearch()` → POST `/search` → `main.py search_route` → `run_in_threadpool(search, ...)` → `searcher.py search()`:
- normalise_arabic on query
- embed_queries to get query vector
- cosine_sim against all_embeddings matrix
- keyword_boost using tag_index
- sort, threshold filter, extract highlights
- return results

→ `renderCards()` in search.js → `initChatWithResults()` → chat popup appears

User sends chat message → `chat.js sendPopupChat()` → POST `/chat` with session_id → `main.py chat_route` → session history retrieved → `run_in_threadpool(chat, history, ...)` → `chatbot.py chat()` → Groq API → response appended to session → returned to frontend → displayed in popup
