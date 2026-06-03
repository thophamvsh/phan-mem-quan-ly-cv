import os
import django
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

# Set logging to see warnings
logging.basicConfig(level=logging.INFO)

from documents.models import Document, DocumentChunk
from documents.services.embeddings import get_embedding, cosine_similarity
from documents.services.retrieval import search_documents
from django.contrib.auth import get_user_model

def run():
    User = get_user_model()
    user = User.objects.first()
    print(f"User: {user.username if user else 'None'}")
    
    query = "Vận hành hồ Sông Hinh trong thời kỳ sử dụng nước gia tăng?"
    
    print("\n--- Testing get_embedding behavior inside container ---")
    # Let's inspect if the returned embedding is from OpenAI or Fallback Hash
    # The hash embedding has a lot of 0.0 values since it only hashes the words.
    # An OpenAI embedding is fully dense (almost no 0.0 values).
    emb = get_embedding(query)
    zeros = sum(1 for val in emb if val == 0.0)
    print(f"Embedding length: {len(emb)}")
    print(f"Number of exact 0.0 values in embedding: {zeros}")
    if zeros > 500:
        print("-> ALERT: The embedding is a sparse HASH fallback vector! OpenAI API call must have failed.")
    else:
        print("-> SUCCESS: The embedding is a dense vector, likely from OpenAI.")
        
    print("\n--- Running retrieval search ---")
    results = search_documents(user, query, limit=5)
    print(f"Search results count: {len(results)}")
    for i, r in enumerate(results, start=1):
        print(f"{i}. Score: {r['score']} | Document: {r['document_title']} | Chunk index: {r['chunk_index']}")
        print(f"   Content snippet: {r['content'][:120]}...")

if __name__ == "__main__":
    run()
