from types import MethodType

from app.services.tiered_retriever import (
    TieredRetriever,
    _explicit_5gs_reference_point,
)


def _n1_result():
    return {
        "distance": 0.12,
        "text": (
            "N1: Reference point between "
            "the UE and the AMF. "
            "NAS signalling is carried "
            "using this reference point."
        ),
        "metadata": {
            "org": "3GPP",
            "code": "TS 23.501",
            "version": "20.2.0",
            "clause": "4.2.7",
            "clause_title": "Reference points",
            "source_id": "ts23501-n1",
        },
    }


def test_detects_explicit_n1_reference_point():
    assert (
        _explicit_5gs_reference_point(
            "5G sisteminde N1 referans noktas? nedir?"
        )
        == "N1"
    )


def test_detects_english_reference_point():
    assert (
        _explicit_5gs_reference_point(
            "What is the N2 reference point?"
        )
        == "N2"
    )


def test_does_not_route_bare_n_token():
    assert (
        _explicit_5gs_reference_point(
            "N1 ?zerinden veri ge?iyor mu?"
        )
        is None
    )


def test_reference_point_uses_priority_ts23501_when_available():
    retriever = (
        TieredRetriever.__new__(
            TieredRetriever
        )
    )

    retriever.priority_enabled = True

    retriever._priority_documents = [
        {
            "org": "ATIS",
            "code": "0700043",
            "title": "WEA",
        },
        {
            "org": "3GPP",
            "code": "TS 23.501",
            "title": (
                "System Architecture "
                "for the 5G System"
            ),
        },
    ]

    priority_calls = []

    def fake_priority_search(
        self,
        *,
        query,
        top_k,
        where,
        routed_documents,
        collection=None,
    ):
        priority_calls.append(
            list(
                routed_documents
                or []
            )
        )

        return [
            _n1_result()
        ]

    retriever._priority_search = (
        MethodType(
            fake_priority_search,
            retriever,
        )
    )

    results = retriever.search(
        query=(
            "5G sisteminde N1 referans noktas? "
            "hangi iki a? fonksiyonu aras?nda "
            "kullan?l?r ve temel g?revi nedir?"
        ),
        top_k=12,
        domain="telecom",
    )

    assert results

    assert (
        results[0]["metadata"]["code"]
        == "TS 23.501"
    )

    assert priority_calls

    for routed_documents in priority_calls:

        assert all(
            document.get("org")
            == "3GPP"
            and document.get("code")
            == "TS 23.501"
            for document
            in routed_documents
        )


class _FakeBackRetriever:

    def __init__(self):
        self.calls = []

    def search(
        self,
        *,
        query,
        top_k,
        where,
    ):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "where": where,
            }
        )

        return [
            _n1_result()
        ]


def test_reference_point_falls_back_to_main_ts23501():
    retriever = (
        TieredRetriever.__new__(
            TieredRetriever
        )
    )

    retriever.priority_enabled = True

    # Production durumu:
    # TS 23.501 priority shelf'te yok.
    retriever._priority_documents = [
        {
            "org": "ATIS",
            "code": "0700043",
            "title": "WEA",
        },
    ]

    back = _FakeBackRetriever()

    retriever.back_retriever = back

    results = retriever.search(
        query=(
            "5G sisteminde N1 referans noktas? "
            "hangi iki a? fonksiyonu aras?nda "
            "kullan?l?r ve temel g?revi nedir?"
        ),
        top_k=12,
        domain="telecom",
    )

    assert results

    assert (
        results[0]["metadata"]["org"]
        == "3GPP"
    )

    assert (
        results[0]["metadata"]["code"]
        == "TS 23.501"
    )

    assert back.calls

    for call in back.calls:

        assert (
            call["where"]
            == {
                "$and": [
                    {
                        "org": "3GPP"
                    },
                    {
                        "code": "TS 23.501"
                    },
                ]
            }
        )


def test_reference_point_back_fallback_keeps_n1_direct_evidence_first():
    retriever = (
        TieredRetriever.__new__(
            TieredRetriever
        )
    )

    retriever.priority_enabled = True
    retriever._priority_documents = []

    class BackWithNoise:

        def search(
            self,
            *,
            query,
            top_k,
            where,
        ):
            return [
                {
                    "distance": 0.05,
                    "text": (
                        "General 5G System "
                        "architecture information."
                    ),
                    "metadata": {
                        "org": "3GPP",
                        "code": "TS 23.501",
                        "clause": "4.1",
                        "clause_title": (
                            "General concepts"
                        ),
                        "source_id": "general",
                    },
                },
                _n1_result(),
            ]

    retriever.back_retriever = (
        BackWithNoise()
    )

    results = retriever.search(
        query=(
            "N1 reference point between "
            "which network functions?"
        ),
        top_k=12,
        domain="telecom",
    )

    assert (
        results[0]["metadata"]["source_id"]
        == "ts23501-n1"
    )
