import json
import os
import re
import pickle
import hashlib
import numpy as np
from embedder import embed_passages

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "opportunities.json")
CACHE_PATH = os.path.join(BASE_DIR, "data", "embeddings.pkl")

MODEL_NAME = "intfloat/multilingual-e5-large"


def hash_json(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_opportunities(path: str = DATA_PATH) -> tuple[list, np.ndarray]:

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    current_hash = hash_json(path)
    descriptions = [o["description"] for o in data]

    cache_valid = False
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "rb") as f:
            cached = pickle.load(f)
        if (
            cached.get("hash") == current_hash
            and cached.get("model") == MODEL_NAME
            and len(cached["embeddings"]) == len(data)
        ):
            embeddings = cached["embeddings"]
            cache_valid = True
            print(f"Cache hit — loaded {len(embeddings)} embeddings (model={MODEL_NAME})")
        else:
            print("Cache stale (data or model changed) — recomputing...")

    if not cache_valid:
        print(f"Computing embeddings with {MODEL_NAME} — takes ~20-30s on first run...")
        embeddings = embed_passages(descriptions)
        with open(CACHE_PATH, "wb") as f:
            pickle.dump(
                {"hash": current_hash, "model": MODEL_NAME, "embeddings": embeddings},
                f,
            )
        print("Embeddings cached to disk.")

    embeddings_matrix = np.array(embeddings)

    return data, embeddings_matrix


# inverted tag index for O(1) guaranteed retrieval

def build_tag_index(opportunities: list) -> dict:
    
    #build  inverted index mapping 
    
    index: dict[str, list[str]] = {}

    for opp in opportunities:
        opp_id = opp.get("id")
        if not opp_id:
            continue

        text_sources = [
            opp.get("title", ""),
            opp.get("title_ar", ""),
            opp.get("organisation", ""),
            opp.get("location", ""),
        ]

        # indexing tags as complete phrases 
        for tag in opp.get("tags", []):
            text_sources.append(tag)
            tag_clean = tag.lower().strip()
            if len(tag_clean) >= 3:
                index.setdefault(tag_clean, [])
                if opp_id not in index[tag_clean]:
                    index[tag_clean].append(opp_id)

        # indexing individual words from all sources
        combined = " ".join(text_sources).lower()
        words = set(re.findall(r'\w+', combined))
        for word in words:
            if len(word) >= 3:
                index.setdefault(word, [])
                if opp_id not in index[word]:
                    index[word].append(opp_id)

    print(f"Tag index built — {len(index):,} unique terms across {len(opportunities)} opportunities")
    return index