import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from documents.models import Document, DocumentChunk

def check():
    docs = Document.objects.all()
    print(f"--- POSTGRES DB DOCUMENTS ---")
    for d in docs:
        chunk = d.chunks.first()
        emb_len = len(chunk.embedding) if chunk and chunk.embedding else 0
        print(f"ID: {d.id} | Title: {d.title} | Status: {d.status} | Chunks: {d.chunks.count()} | First Chunk Embedding Size: {emb_len}")

if __name__ == "__main__":
    check()
