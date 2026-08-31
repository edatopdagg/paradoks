import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class VersionIdentity:
    version: str
    release: str
    source_filename: str


def _source_filename(source_url: str) -> str:
    path = unquote(urlparse(source_url).path)
    return PurePosixPath(path).name


def _base36_character(value: str) -> int:
    character = value.casefold()
    if character.isdigit():
        return int(character)
    if "a" <= character <= "z":
        return ord(character) - ord("a") + 10
    raise ValueError(f"Geçersiz 3GPP sürüm karakteri: {value}")


def _infer_3gpp(code: str, source_url: str) -> VersionIdentity:
    filename = _source_filename(source_url)
    match = re.fullmatch(
        r"(?P<number>\d{5})-(?P<version>[0-9a-zA-Z]{3})\.zip",
        filename,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"3GPP arşiv adı çözülemedi: {filename}")

    expected_number = "".join(re.findall(r"\d", code))
    if expected_number and expected_number != match.group("number"):
        raise ValueError(
            "3GPP belge kodu ile arşiv adı eşleşmiyor: "
            f"{code} != {filename}"
        )

    encoded = match.group("version")
    major, minor, patch = (_base36_character(value) for value in encoded)
    return VersionIdentity(
        version=f"{major}.{minor}.{patch}",
        release=str(major),
        source_filename=filename,
    )


def _infer_etsi(source_url: str) -> VersionIdentity:
    filename = _source_filename(source_url)
    match = re.search(
        r"v(?P<major>\d{2})(?P<minor>\d{2})(?P<patch>\d{2})p\.pdf$",
        filename,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"ETSI PDF sürümü çözülemedi: {filename}")

    return VersionIdentity(
        version=(
            f"{int(match.group('major'))}."
            f"{int(match.group('minor'))}."
            f"{int(match.group('patch'))}"
        ),
        release="",
        source_filename=filename,
    )


def _infer_ietf(code: str, source_url: str) -> VersionIdentity:
    filename = _source_filename(source_url)
    match = re.search(r"(?:rfc\s*)?(\d{3,5})", code, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"IETF RFC kodu çözülemedi: {code}")
    number = match.group(1)
    return VersionIdentity(
        version=f"RFC {number}",
        release="",
        source_filename=filename,
    )


def infer_version_identity(
    *,
    org: str,
    code: str,
    source_url: str,
) -> VersionIdentity:
    organization = " ".join((org or "").split()).upper()
    if organization == "3GPP":
        return _infer_3gpp(code, source_url)
    if organization == "ETSI":
        return _infer_etsi(source_url)
    if organization == "IETF":
        return _infer_ietf(code, source_url)
    return VersionIdentity(
        version="",
        release="",
        source_filename=_source_filename(source_url),
    )
