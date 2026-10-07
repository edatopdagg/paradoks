from app.services.tiered_retriever import (
    _is_ngap_write_replace_intent,
)


def test_basic_5g_write_replace_ie_question_routes_to_ngap():
    assert (
        _is_ngap_write_replace_intent(
            "5G write replace mesajını gönderebilmem "
            "için hangi IE'ler olmalı?"
        )
        is True
    )


def test_rewritten_basic_query_routes_to_ngap():
    assert (
        _is_ngap_write_replace_intent(
            "write-replace message Information Elements "
            "3GPP. IE 5G"
        )
        is True
    )


def test_full_normative_name_still_routes_to_ngap():
    assert (
        _is_ngap_write_replace_intent(
            "5G NGAP WRITE-REPLACE WARNING REQUEST "
            "Information Elements"
        )
        is True
    )


def test_non_5g_write_replace_is_not_forced_to_ngap():
    assert (
        _is_ngap_write_replace_intent(
            "write replace operation in a text editor"
        )
        is False
    )


def test_5g_without_write_replace_is_not_matched():
    assert (
        _is_ngap_write_replace_intent(
            "5G registration mesajındaki IE'ler nelerdir?"
        )
        is False
    )
