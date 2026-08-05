# Paradoks

Paradoks, 3GPP ve diğer telekomünikasyon standartlarına dayanarak kaynak kontrollü cevaplar üreten bir yapay zekâ asistanıdır.

Sistem, kullanıcının sorusuyla ilgili standart maddelerini bulur, yeniden sıralar ve seçilen kaynaklara dayanarak Türkçe cevap üretir.

## Mevcut Sistem

```text
Kullanıcı sorusu
→ Embedding
→ ChromaDB
→ Mesafe filtresi
→ Reranker
→ Prompt Builder
→ Ollama
→ Cevap ve kaynaklar
```

## Kullanılan Teknolojiler

- Python
- FastAPI
- ChromaDB
- Sentence Transformers
- Ollama
- Swagger

## Kullanılan Modeller

```text
Embedding: intfloat/multilingual-e5-small
Reranker: BAAI/bge-reranker-v2-m3
LLM: qwen3.5:2b-q4_K_M
```

## Kurulum

### 1. Projeyi klonla

```powershell
git clone https://github.com/kevserkatircioglu/paradoks.git
cd paradoks
cd backend
```

### 2. Sanal ortam oluştur ve etkinleştir

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Paketleri kur

```powershell
pip install -r requirements.txt
```

### 4. Ollama'yı kur

```powershell
irm https://ollama.com/install.ps1 | iex
```

Kurulumu kontrol et:

```powershell
ollama --version
```

### 5. LLM modelini indir

```powershell
ollama pull qwen3.5:2b-q4_K_M
```

### 6. Mock vektör veritabanını oluştur

```powershell
python scripts/build_mock_vector_db.py
```

### 7. FastAPI sunucusunu başlat

```powershell
uvicorn app.main:app --reload
```

Swagger arayüzü:

```text
http://127.0.0.1:8000/docs
```

## API Kullanımı

### POST `/chat`

İstek:

```json
{
  "message": "Cell Broadcast uyarı mesajı nasıl iptal edilir?"
}
```

Cevap:

```json
{
  "reply": "Cell Broadcast uyarı mesajını iptal etmek için message identifier ve serial number içeren bir cancellation request gönderilmelidir.",
  "sources": [
    {
      "org": "3GPP",
      "code": "TS 23.041",
      "version": "20.0.0",
      "clause": "9.1.3.4.2"
    }
  ],
  "blocked_sources": []
}
```

## Veri Formatı

Gerçek dokümanlardan oluşturulacak her chunk aşağıdaki yapıya uymalıdır:

```json
{
  "chunk_id": "benzersiz_kimlik",
  "text": "Standart maddesinden alınan metin",
  "org": "3GPP",
  "code": "TS 23.041",
  "version": "20.0.0",
  "clause": "9.1.3.4.2",
  "status": "available",
  "source_url": "resmi kaynak bağlantısı"
}
```

## Mevcut Durum

- FastAPI backend çalışıyor.
- ChromaDB retrieval çalışıyor.
- Mesafe filtresi çalışıyor.
- Reranker doğru maddeyi üst sıraya taşıyor.
- Ollama entegrasyonu çalışıyor.
- Kaynak bulunmadığında sistem cevap üretmiyor.
- Sistem şu anda mock verilerle test ediliyor.

## Sonraki Adımlar

- Gerçek 3GPP verilerinin entegrasyonu
- Otomatik testler
- Hata yönetimi
- `.env` yapılandırması
- Daha güçlü LLM
- Kullanıcı arayüzü