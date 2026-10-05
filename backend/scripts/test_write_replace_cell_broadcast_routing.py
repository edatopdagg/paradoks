from app.services.tiered_retriever import (
    _is_cell_broadcast_intent,
)


def test_literal_cell_broadcast_is_detected():
    assert _is_cell_broadcast_intent(
        "Cell Broadcast Service serial number"
    )


def test_cbs_is_detected():
    assert _is_cell_broadcast_intent(
        "CBS serial number field"
    )


def test_write_replace_warning_request_is_detected():
    assert _is_cell_broadcast_intent(
        "Write-Replace-Warning-Request "
        "message Information Elements 3GPP IE"
    )


def test_write_replace_warning_indication_is_detected():
    assert _is_cell_broadcast_intent(
        "WRITE-REPLACE-WARNING-INDICATION-NG-RAN"
    )


def test_public_warning_terms_are_detected():
    for query in (
        "PWS warning delivery",
        "ETWS primary notification",
        "CMAS alert message",
        "CBCF warning procedure",
    ):
        assert _is_cell_broadcast_intent(
            query
        )


def test_unrelated_telecom_query_is_not_detected():
    assert not _is_cell_broadcast_intent(
        "5G PDU Session Establishment Request"
    )


def test_ngap_write_replace_intent_v1():
    from app.services.tiered_retriever import (
        _is_ngap_write_replace_intent,
    )

    assert _is_ngap_write_replace_intent(
        "5G Write-Replace-Warning-Request "
        "message Information Elements"
    )

    assert _is_ngap_write_replace_intent(
        "NGAP Write-Replace-Warning-Request IEs"
    )

    assert _is_ngap_write_replace_intent(
        "NG-RAN Write Replace Warning Request"
    )


def test_legacy_write_replace_is_not_forced_to_ngap():
    from app.services.tiered_retriever import (
        _is_ngap_write_replace_intent,
    )

    assert not _is_ngap_write_replace_intent(
        "GSM BSC CBC Write-Replace message"
    )


def test_ngap_exact_route_exists():
    from pathlib import Path

    text = Path(
        "app/services/tiered_retriever.py"
    ).read_text(
        encoding="utf-8",
    )

    assert (
        "PARADOKS_NGAP_WRITE_REPLACE_EXACT_ROUTE_V1"
        in text
    )

    assert (
        "TS 38.413"
        in text
    )

    assert (
        "WriteReplaceWarningRequestIEs"
        in text
    )


def test_ngap_exact_chroma_recovery_v1():
    from pathlib import Path

    text = Path(
        "app/services/tiered_retriever.py"
    ).read_text(
        encoding="utf-8",
    )

    assert (
        "PARADOKS_NGAP_WRITE_REPLACE_EXACT_CHROMA_V1"
        in text
    )

    assert (
        ".collection"
        in text
    )

    assert (
        "writereplacewarningrequesties"
        in text
    )

    assert (
        "concurrentwarningmessageind"
        in text
    )

    assert (
        "warningareacoordinates"
        in text
    )
