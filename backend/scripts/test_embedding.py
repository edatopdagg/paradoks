from app.services.embedding_service import EmbeddingService


embedding_service = EmbeddingService()

query = "Cell Broadcast mesajı nasıl iptal edilir?"

vector = embedding_service.embed_query(query)

print(f"Soru: {query}")
print(f"Vektör boyutu: {len(vector)}")
print(f"İlk 10 değer: {vector[:10]}")