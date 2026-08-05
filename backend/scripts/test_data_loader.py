from app.services.data_loader import load_chunks


chunks = load_chunks()

print(f"Toplam chunk sayısı: {len(chunks)}")

for chunk in chunks:
    print("-" * 50)
    print(f"ID: {chunk['chunk_id']}")
    print(f"Belge: {chunk['org']} {chunk['code']}")
    print(f"Madde: {chunk['clause']}")
    print(f"Metin: {chunk['text']}")