"""
Ask a question, get a live-searched, cited answer. No pre-crawling,
no database -- searches the web at question time.

Usage:
    python ask.py "Cell Broadcast'te warning message nasil iptal edilir?"

Requires in .env:
    GOOGLE_API_KEY=...
    GOOGLE_CX=...
    ANTHROPIC_API_KEY=...
"""

import os
import sys
import requests
from dotenv import load_dotenv
from anthropic import Anthropic

sys.path.insert(0, "src")
from fetcher import fetch_and_read
from reference_parser import parse_references_section

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")
client = Anthropic()  # reads ANTHROPIC_API_KEY from env

# Only these domains -- keeps results to official standards, not blogs/forums
STANDARDS_DOMAINS = ["3gpp.org", "etsi.org", "ietf.org", "itu.int", "gsma.com", "atis.org"]
SITE_FILTER = " OR ".join(f"site:{d}" for d in STANDARDS_DOMAINS)


def search_web(query: str, num_results: int = 3) -> list[dict]:
    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CX, "q": query, "num": num_results},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def gather_context(question: str) -> list[dict]:
    results = search_web(f"{question} ({SITE_FILTER})")
    context = []
    for r in results:
        url = r.get("link")
        text = fetch_and_read(url)
        if not text:
            continue
        context.append({"title": r.get("title"), "url": url, "text": text[:8000]})

        # one extra hop: if this doc references another spec by name, and
        # that spec's number appears in the question too, pull it in as
        # extra context -- catches "what does X say" questions accurately
        for ref in parse_references_section(text):
            if ref.code.replace(" ", "") in question.replace(" ", ""):
                extra = search_web(f"{ref.org} {ref.code} ({SITE_FILTER})", num_results=1)
                if extra:
                    extra_text = fetch_and_read(extra[0]["link"])
                    if extra_text:
                        context.append({
                            "title": f"{ref.org} {ref.code}: {ref.title}",
                            "url": extra[0]["link"],
                            "text": extra_text[:8000],
                        })
    return context


def answer_question(question: str) -> str:
    context = gather_context(question)
    if not context:
        return "İlgili bir kaynak bulamadım."

    context_block = "\n\n".join(
        f"[{i+1}] {c['title']} ({c['url']})\n{c['text']}" for i, c in enumerate(context)
    )

    prompt = (
        "Sen bir telekomunikasyon standartlari uzmanisin. Asagidaki resmi "
        "standart belgelerinden alinan parcalara dayanarak soruyu cevapla. "
        "SADECE bu kaynaklardaki bilgiyi kullan, genel bilginle doldurma. "
        "Kisa ve net cevap ver, hangi standart/madde oldugunu belirt, "
        "cevabinin sonunda [1], [2] gibi kaynak numaralarini goster.\n\n"
        f"Kaynaklar:\n{context_block}\n\nSoru: {question}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Soru: ")
    print(answer_question(question))
