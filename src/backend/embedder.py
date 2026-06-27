import logging
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
MODEL_NAME = "intfloat/multilingual-e5-large"

logger.info(f"Loading model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)
logger.info("Model loaded successfully")

def embed_queries(texts: list[str], batch_size: int = 64) -> np.ndarray:
    
    prefixed = ["query: " + t for t in texts]
    return model.encode(prefixed, normalize_embeddings=True, batch_size=batch_size)

def embed_passages(texts: list[str], batch_size: int = 64) -> np.ndarray:
    
    prefixed = ["passage: " + t for t in texts]
    return model.encode(prefixed, normalize_embeddings=True, batch_size=batch_size)