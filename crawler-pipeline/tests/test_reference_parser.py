import sys
sys.path.insert(0, "src")

from reference_parser import parse_reference_line


def test_3gpp_reference():
    ref = parse_reference_line('[2]\t3GPP TS 22.003: "Circuit Teleservices supported by a Public Land Mobile Network (PLMN)".')
    assert ref.org == "3GPP"
    assert ref.code == "TS 22.003"


def test_ietf_reference():
    ref = parse_reference_line('[33]\tIETF RFC 4960: "Stream Control Transmission Protocol".')
    assert ref.org == "IETF"
    assert ref.code == "4960"


def test_atis_reference():
    ref = parse_reference_line('[47]\tATIS-0700041: "WEA 3.0: Device-Based Geo-Fencing".')
    assert ref.org == "ATIS"
    assert ref.code == "0700041"


def test_gsma_reference():
    ref = parse_reference_line('[25]\tGSMA AD.26: "Coding of Cell Broadcast Functions".')
    assert ref.org == "GSMA"
    assert ref.code == "AD.26"


def test_itu_t_reference():
    ref = parse_reference_line('[12]\tITU-T Recommendation X.210: "Information technology".')
    assert ref.org == "ITU-T"
    assert ref.code == "X.210"


def test_void_reference_returns_none():
    assert parse_reference_line("[1]\tVoid") is None


def test_nbsp_normalization():
    line = "[38]\t3GPP\xa0TS\xa023.007: \"Restoration Procedures\"."
    ref = parse_reference_line(line)
    assert ref.org == "3GPP"
    assert ref.code == "TS 23.007"
