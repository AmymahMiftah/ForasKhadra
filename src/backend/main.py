

import uuid
import logging
from collections import defaultdict

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chatbot import chat
from data_loader import load_opportunities, build_tag_index
from searcher import search, filter_expired

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Foras Khadra — Smart Search + AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

all_opportunities, all_embeddings = load_opportunities()


# ── Filter expired — slices matrix in sync with list ──
def filter_expired_with_embeddings(
    opportunities: list, embeddings: np.ndarray
) -> tuple[list, np.ndarray]:
    from datetime import date
    today = date.today()
    active_opps, active_indices = [], []
    for i, o in enumerate(opportunities):
        deadline_str = o.get("deadline", "")
        keep = True
        if deadline_str:
            try:
                keep = date.fromisoformat(deadline_str) >= today
            except ValueError:
                pass
        if keep:
            active_opps.append(o)
            active_indices.append(i)
    active_emb = embeddings[active_indices] if active_indices else embeddings[:0]
    return active_opps, active_emb


active_opportunities, active_embeddings = filter_expired_with_embeddings(
    all_opportunities, all_embeddings
)
expired_count = len(all_opportunities) - len(active_opportunities)

tag_index = build_tag_index(active_opportunities)

from embedder import embed_queries
embed_queries(["warmup"])
logger.info("Model warmed up — ready for fast search")

logger.info(
    f"Server ready — {len(active_opportunities)} active opportunities "
    f"({expired_count} expired filtered at startup) | "
    f"{len(tag_index):,} terms in tag index"
)


SESSION_MAX_TURNS = 20
session_store: dict[str, list] = defaultdict(list)



class SearchRequest(BaseModel):
    query: str
    top_k: int = 15


class ChatRequest(BaseModel):
    session_id: str | None = None   # new session
    message: str                     # only the new user message



@app.post("/search")
async def search_route(body: SearchRequest):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    top_k = None if body.top_k == -1 else min(max(body.top_k, 1), 50)
    logger.info(f"Search: {body.query!r} | top_k={top_k}")
    return await run_in_threadpool(
        search, body.query, active_opportunities, active_embeddings, top_k, False
    )


@app.post("/chat")
async def chat_route(body: ChatRequest):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(body.message) > 500:
        raise HTTPException(status_code=400, detail="Message too long (max 500 chars)")

    # Resume or create session
    session_id = body.session_id or str(uuid.uuid4())
    history = session_store[session_id]

    # Append new user message
    history.append({"role": "user", "content": body.message})

    # Trim to avoid token overflow
    max_messages = SESSION_MAX_TURNS * 2
    if len(history) > max_messages:
        history = history[-max_messages:]
        session_store[session_id] = history

    logger.info(
        f"Chat session={session_id} | history_len={len(history)} | last={body.message!r}"
    )

    try:
        result = await run_in_threadpool(
            chat,
            history,
            active_opportunities,
            active_embeddings,
            tag_index,
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        history.pop()   # remove failed user turn so session stays clean
        raise HTTPException(status_code=500, detail=str(e))

    # Persist assistant reply
    session_store[session_id].append({
        "role": "assistant",
        "content": result["answer"],
    })

    return {
        "session_id": session_id,
        "answer":result["answer"],
        "sources":result["sources"],
    }


@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    session_store.pop(session_id, None)
    logger.info(f"Session cleared: {session_id}")
    return {"cleared": session_id}


@app.get("/health")
async def health():
    return {
        "status":"ok",
        "active":len(active_opportunities),
        "expired_filtered": expired_count,
        "tag_index_terms":  len(tag_index),
        "active_sessions":  len(session_store),
    }