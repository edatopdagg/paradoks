

from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any

from models import (
    DocStatus,
    Reference,
    ResolvedSource,
)
from reference_parser import (
    parse_references_section,
)
from resolver import resolve
from fetcher import fetch_and_read

import re

def detect_3gpp_document_id(text: str) -> tuple[str, str] | None:
    """Metnin ilk 80 satırına bakarak standardın gerçek kimliğini tespit eder."""
    head = "\n".join((text or "").splitlines()[:80])
    match = re.search(
        r"\b3GPP\s+(TS|TR)\s+(\d{2}\.\d{3})\b",
        head,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    doc_type = match.group(1).upper()
    number = match.group(2)
    return ("3GPP", f"{doc_type} {number}")

def validate_3gpp_document(requested_code: str, text: str) -> bool:
    """İstenen standart ile indirilen belgenin eşleşip eşleşmediğini doğrular."""
    detected = detect_3gpp_document_id(text)
    if detected is None:
        return False

    detected_code = detected[1].upper().strip()
    requested = requested_code.upper().strip()
    return detected_code == requested


def looks_like_3gpp_meeting_contribution(text: str) -> bool:
    """Metnin bir 3GPP toplantı katkısı (meeting contribution) olup olmadığını kontrol eder."""
    head = "\n".join((text or "").splitlines()[:50]).casefold()
    markers = [
        "3gpp tsg-",
        "meeting #",
        "sp-",
        "rp-",
        "cp-",
        "gp-",
    ]
    matches = sum(marker in head for marker in markers)
    return matches >= 2
    
class Crawler:
    def __init__(
        self,
        cache_dir: str | Path | None = None,
    ):
        # -------------------------------------------------
        # QUEUE
        # -------------------------------------------------
        self.queue: deque[Reference] = deque()

        # -------------------------------------------------
        # VISITED
        # -------------------------------------------------
        self.visited_codes: set[
            tuple[str, str]
        ] = set()

        # -------------------------------------------------
        # RESOLVED RESULTS
        # -------------------------------------------------
        self.results: list[ResolvedSource] = []

        # -------------------------------------------------
        # DOCUMENT TEXTS
        #
        # main.py şu anda bunları chunker'a göndermek için
        # kullanıyor. Bu nedenle RAM yapısını koruyoruz.
        # Ancak aynı metin artık ayrıca diske de cache edilir.
        # -------------------------------------------------
        self.documents: dict[
            tuple[str, str],
            str,
        ] = {}

        # -------------------------------------------------
        # CACHE
        # -------------------------------------------------
        if cache_dir is None:
            base_dir = (
                Path(__file__)
                .resolve()
                .parent
                .parent
            )

            self.cache_dir = (
                base_dir
                / "data"
                / "crawler_cache"
            )

        else:
            self.cache_dir = Path(
                cache_dir
            )

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            "[CRAWLER] Cache:",
            self.cache_dir.resolve(),
        )

        self.cache_hits = 0
        self.cache_misses = 0

    # -----------------------------------------------------
    # HELPERS
    # -----------------------------------------------------

    def _make_cache_id(
        self,
        org: str,
        code: str,
    ) -> str:
        """
        Organizasyon + belge kodundan güvenli dosya adı üretir.
        """

        raw = (
            f"{org.strip().upper()}|"
            f"{code.strip().upper()}"
        )

        digest = hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()

        return digest

    def _cache_path(
        self,
        org: str,
        code: str,
    ) -> Path:
        cache_id = (
            self._make_cache_id(
                org,
                code,
            )
        )

        return (
            self.cache_dir
            / f"{cache_id}.json"
        )

    def _reference_to_dict(
        self,
        ref: Reference,
    ) -> dict[str, str]:
        return {
            "org": ref.org,
            "code": ref.code,
            "title": (
                getattr(
                    ref,
                    "title",
                    "",
                )
                or ""
            ),
            "raw_text": (
                getattr(
                    ref,
                    "raw_text",
                    "",
                )
                or ""
            ),
        }

    def _reference_from_dict(
        self,
        data: dict[str, Any],
    ) -> Reference:
        return Reference(
            org=str(
                data.get(
                    "org",
                    "",
                )
            ),
            code=str(
                data.get(
                    "code",
                    "",
                )
            ),
            title=str(
                data.get(
                    "title",
                    "",
                )
            ),
            raw_text=str(
                data.get(
                    "raw_text",
                    "",
                )
            ),
        )

    def _status_to_string(
        self,
        status: Any,
    ) -> str:
        if hasattr(
            status,
            "value",
        ):
            return str(
                status.value
            )

        return str(
            status
        )

    def _status_from_string(
        self,
        value: str,
    ) -> DocStatus:
        """
        Cache'deki string status'u DocStatus'a çevirir.
        """

        for status in DocStatus:
            if (
                self._status_to_string(
                    status
                )
                == value
            ):
                return status

        # Cache beklenmeyen/eski değer içerirse
        # güvenli şekilde unresolved kabul et.
        return DocStatus.UNRESOLVED

    # -----------------------------------------------------
    # CACHE WRITE
    # -----------------------------------------------------

    def _save_cache(
        self,
        ref: Reference,
        resolved: ResolvedSource,
        text: str | None,
        discovered_refs: list[Reference],
    ) -> None:
        """
        Bir crawler sonucunu JSON olarak diske kaydeder.

        Saklananlar:
        - resolved URL
        - version
        - status
        - çıkarılmış tam text
        - doküman içinden keşfedilen referanslar
        """

        cache_path = (
            self._cache_path(
                ref.org,
                ref.code,
            )
        )

        payload = {
            "reference": (
                self._reference_to_dict(
                    ref
                )
            ),
            "resolved": {
                "status": (
                    self._status_to_string(
                        resolved.status
                    )
                ),
                "source_url": (
                    resolved.source_url
                    or ""
                ),
                "version": (
                    resolved.version
                    or ""
                ),
            },
            "text": (
                text
                or ""
            ),
            "discovered_refs": [
                self._reference_to_dict(
                    new_ref
                )
                for new_ref
                in discovered_refs
            ],
        }

        temp_path = (
            cache_path.with_suffix(
                ".tmp"
            )
        )

        try:
            temp_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            temp_path.replace(
                cache_path
            )

        except OSError as error:
            print(
                "[CRAWLER] Cache yazılamadı:",
                ref.org,
                ref.code,
                "|",
                error,
            )

            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass

    # -----------------------------------------------------
    # CACHE READ
    # -----------------------------------------------------

    def _load_cache(
        self,
        ref: Reference,
    ) -> dict[str, Any] | None:
        cache_path = (
            self._cache_path(
                ref.org,
                ref.code,
            )
        )

        if not cache_path.exists():
            return None

        try:
            data = json.loads(
                cache_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

        if not isinstance(
            data,
            dict,
        ):
            return None

        return data

    def _restore_from_cache(
        self,
        ref: Reference,
        cached: dict[str, Any],
    ) -> bool:
        """
        Cache kaydını crawler state'ine geri yükler.

        Başarılıysa True döner.
        """

        try:
            resolved_data = (
                cached.get(
                    "resolved",
                    {},
                )
            )

            status = (
                self._status_from_string(
                    str(
                        resolved_data.get(
                            "status",
                            "",
                        )
                    )
                )
            )

            resolved = ResolvedSource(
                reference=ref,
                status=status,
                source_url=(
                    resolved_data.get(
                        "source_url"
                    )
                    or None
                ),
                version=(
                    resolved_data.get(
                        "version"
                    )
                    or None
                ),
            )

            self.results.append(
                resolved
            )

            text = str(
                cached.get(
                    "text",
                    "",
                )
                or ""
            )

            key = (
                ref.org,
                ref.code,
            )

            if text:
                self.documents[
                    key
                ] = text

            discovered_data = (
                cached.get(
                    "discovered_refs",
                    [],
                )
            )

            discovered_refs: list[
                Reference
            ] = []

            if isinstance(
                discovered_data,
                list,
            ):
                for item in discovered_data:
                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    try:
                        discovered_refs.append(
                            self._reference_from_dict(
                                item
                            )
                        )

                    except Exception:
                        continue

            for new_ref in discovered_refs:
                new_key = (
                    new_ref.org,
                    new_ref.code,
                )

                if (
                    new_key
                    not in self.visited_codes
                ):
                    self.queue.append(
                        new_ref
                    )

            return True

        except Exception as error:
            print(
                "[CRAWLER] Cache restore hatası:",
                ref.org,
                ref.code,
                "|",
                error,
            )

            return False

    # -----------------------------------------------------
    # SEED
    # -----------------------------------------------------

    def seed(
        self,
        seed_references: list[Reference],
    ) -> None:
        """
        Başlangıç referanslarını queue'ya ekler.
        """

        for ref in seed_references:
            self.queue.append(
                ref
            )

    # -----------------------------------------------------
    # RUN
    # -----------------------------------------------------

    def run(
        self,
    ) -> list[ResolvedSource]:
        """
        Recursive crawler ana döngüsü.

        Öncelik sırası:

        1. visited kontrolü
        2. disk cache kontrolü
        3. cache yoksa resolver
        4. fetch
        5. reference parse
        6. cache save

        Böylece ikinci çalıştırmada aynı dokümanlar
        internetten tekrar indirilmez.
        """

        while self.queue:

            ref = (
                self.queue.popleft()
            )

            key = (
                ref.org,
                ref.code,
            )

            # -------------------------------------------------
            # VISITED
            # -------------------------------------------------
            if key in self.visited_codes:
                continue

            self.visited_codes.add(
                key
            )

            print(
                f"İşleniyor: "
                f"{ref.org} "
                f"{ref.code}"
            )

            # -------------------------------------------------
            # CACHE
            # -------------------------------------------------
            cached = (
                self._load_cache(
                    ref
                )
            )

            if cached is not None:
                restored = (
                    self._restore_from_cache(
                        ref,
                        cached,
                    )
                )

                if restored:
                    self.cache_hits += 1

                    print(
                        "[CACHE HIT]",
                        ref.org,
                        ref.code,
                    )

                    continue

            self.cache_misses += 1

            # -------------------------------------------------
            # RESOLVE
            # -------------------------------------------------
            resolved = resolve(
                ref
            )

            self.results.append(
                resolved
            )

            # -------------------------------------------------
            # BLOCKED / UNRESOLVED
            # -------------------------------------------------
            if resolved.status in (
                DocStatus.BLOCKED,
                DocStatus.UNRESOLVED,
            ):
                self._save_cache(
                    ref=ref,
                    resolved=resolved,
                    text=None,
                    discovered_refs=[],
                )

                continue

            if not resolved.source_url:
                self._save_cache(
                    ref=ref,
                    resolved=resolved,
                    text=None,
                    discovered_refs=[],
                )

                continue

            # -------------------------------------------------
            # FETCH & VALIDATE
            # -------------------------------------------------
            text = fetch_and_read(
                url=resolved.source_url,
                requested_code=ref.code
            )

            if not text:
                self._save_cache(
                    ref=ref,
                    resolved=resolved,
                    text=None,
                    discovered_refs=[],
                )
                continue

            # Eğer 3GPP belgesi ise, içerik doğrulaması yap
            if ref.org.upper() == "3GPP":
                
                # EK KORUMA (Madde 8): Toplantı notu (Meeting Contribution) kontrolü
                if looks_like_3gpp_meeting_contribution(text):
                    print(f"[REDDEDİLDİ] {ref.code} - Bu bir toplantı notu (Meeting Contribution), standart değil!")
                    self._save_cache(
                        ref=ref,
                        resolved=resolved,
                        text=None,
                        discovered_refs=[],
                    )
                    continue

                # ANA KORUMA (Madde 5, 6, 7): Doğru standart mı kontrolü
                if not validate_3gpp_document(ref.code, text):
                    detected_id = detect_3gpp_document_id(text)
                    print(
                        f"[REDDEDİLDİ] İstenen: {ref.code}, "
                        f"Bulunan: {detected_id}. Yanlış belge atlanıyor."
                    )
                    self._save_cache(
                        ref=ref,
                        resolved=resolved,
                        text=None,
                        discovered_refs=[],
                    )
                    continue

            # Eğer 3GPP belgesi ise, içerik doğrulaması yap
            if ref.org.upper() == "3GPP":
                if not validate_3gpp_document(ref.code, text):
                    detected_id = detect_3gpp_document_id(text)
                    print(
                        f"[REDDEDİLDİ] İstenen: {ref.code}, "
                        f"Bulunan: {detected_id}. Yanlış belge atlanıyor."
                    )
                    # Yanlış belgeyi başarılıymış gibi kaydetme
                    self._save_cache(
                        ref=ref,
                        resolved=resolved,
                        text=None,
                        discovered_refs=[],
                    )
                    continue
            # -------------------------------------------------
            # STORE IN RAM
            # -------------------------------------------------
            self.documents[
                key
            ] = text

            # -------------------------------------------------
            # PARSE REFERENCES
            # -------------------------------------------------
            discovered_refs = (
                parse_references_section(
                    text
                )
            )

            # -------------------------------------------------
            # SAVE CACHE
            # -------------------------------------------------
            self._save_cache(
                ref=ref,
                resolved=resolved,
                text=text,
                discovered_refs=(
                    discovered_refs
                ),
            )

            # -------------------------------------------------
            # QUEUE NEW REFERENCES
            # -------------------------------------------------
            for new_ref in discovered_refs:

                new_key = (
                    new_ref.org,
                    new_ref.code,
                )

                if (
                    new_key
                    not in self.visited_codes
                ):
                    self.queue.append(
                        new_ref
                    )

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------
        print()
        print("=" * 70)
        print(
            "CRAWLER CACHE OZETI"
        )
        print("=" * 70)

        print(
            "Cache hit:",
            self.cache_hits,
        )

        print(
            "Cache miss:",
            self.cache_misses,
        )

        print(
            "Visited:",
            len(
                self.visited_codes
            ),
        )

        print(
            "Document:",
            len(
                self.documents
            ),
        )

        print("=" * 70)

        return self.results
