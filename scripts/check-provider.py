"""Verify the configured REAL provider without logging its URL/key or input."""
import math
from config import EMBEDDING_BASE_URL, EMBEDDING_API_KEY, EMBEDDING_MODEL
from openai import OpenAI

client = OpenAI(base_url=EMBEDDING_BASE_URL, api_key=EMBEDDING_API_KEY, timeout=20, max_retries=0)
try:
    response = client.embeddings.create(input=["InfoChord disposable demo check"], model=EMBEDDING_MODEL)
    vector = response.data[0].embedding
    if not vector or not all(math.isfinite(x) for x in vector):
        raise ValueError("Invalid numeric vector")
    print(f"Embedding provider responded: {len(vector)} finite dimensions")
except Exception as exc:
    raise SystemExit(f"Provider check failed ({type(exc).__name__}); check local configuration and model availability")
