import hashlib
import logging
import math
import os

from django.conf import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
FALLBACK_DIMENSIONS = 1536


def get_embedding(text):
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if api_key:
        try:
            from openai import OpenAI

            response = OpenAI(api_key=api_key).embeddings.create(
                model=EMBEDDING_MODEL,
                input=(text or "")[:8000],
            )
            return list(response.data[0].embedding)
        except Exception:
            logger.exception("OpenAI embedding request failed. Falling back to local hash embedding.")
    return _hash_embedding(text or "")


def cosine_similarity(left, right):
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        logger.warning(
            "Dimension mismatch in cosine similarity calculation: %d vs %d. Falling back to 0.0 score.",
            len(left),
            len(right),
        )
        return 0.0
    size = len(left)
    if not size:
        return 0.0
    dot = sum(float(left[i]) * float(right[i]) for i in range(size))
    left_norm = math.sqrt(sum(float(left[i]) ** 2 for i in range(size)))
    right_norm = math.sqrt(sum(float(right[i]) ** 2 for i in range(size)))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _hash_embedding(text):
    vector = [0.0] * FALLBACK_DIMENSIONS
    for word in text.lower().split():
        digest = hashlib.sha256(word.encode("utf-8", errors="ignore")).digest()
        index = int.from_bytes(digest[:2], "big") % FALLBACK_DIMENSIONS
        sign = 1.0 if digest[2] % 2 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return [_hash_embedding(t or "") for t in texts]

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        batch_size = 256
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = [t[:8000] if t else "" for t in texts[i : i + batch_size]]
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
            )
            for item in response.data:
                embeddings.append(list(item.embedding))
        return embeddings
    except Exception:
        logger.exception("OpenAI batch embedding request failed. Falling back to local hash embedding.")
        return [_hash_embedding(t or "") for t in texts]
