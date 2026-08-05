from app.services.retriever import Retriever


def main() -> None:
    retriever = Retriever()

    question = "Cell Broadcast warning mesajı nasıl iptal edilir?"

    results = retriever.search(
        query=question,
        top_k=3,
    )

    print(f"\nSoru: {question}\n")

    for index, result in enumerate(results, start=1):
        metadata = result["metadata"]

        print("=" * 70)
        print(f"Sonuç: {index}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"Belge: {metadata.get('org')} {metadata.get('code')}")
        print(f"Versiyon: {metadata.get('version')}")
        print(f"Madde: {metadata.get('clause')}")
        print(f"Durum: {metadata.get('status')}")
        print(f"Mesafe: {result['distance']}")
        print(f"Metin: {result['text']}")


if __name__ == "__main__":
    main()