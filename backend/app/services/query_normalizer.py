import re


# =========================================================
# YÜKSEK HASSASİYETLİ İLİŞKİ KURALLARI
# =========================================================
#
# Bu kurallar cevabı sorguya YAZMAZ.
#
# Amaç:
# Kullanıcının Türkçe/gündelik sorusunu,
# standartların kullandığı teknik İngilizce arama
# ifadelerine dönüştürmek.
#
# Örneğin:
#
# AMF-SMF sorusu:
#   "AMF SMF reference point"
#
# Burada "N11" cevabı sorguya eklenmez.
# =========================================================

HIGH_PRECISION_RULES: list[
    tuple[tuple[str, ...], tuple[str, ...]]
] = [

    # -----------------------------------------------------
    # AMF <-> SMF REFERENCE POINT
    # -----------------------------------------------------

    (
        (
            r"\bamf\b.*\bsmf\b.*\breferans\s+nokt",
            r"\bsmf\b.*\bamf\b.*\breferans\s+nokt",
            r"\bamf\b.*\bsmf\b.*\breference\s+point",
            r"\bsmf\b.*\bamf\b.*\breference\s+point",
        ),
        (
            "AMF SMF reference point",
            "reference point between AMF and SMF",
            "5GS reference point representation AMF SMF",
        ),
    ),

    # -----------------------------------------------------
    # NG-RAN <-> AMF PROTOCOL
    # -----------------------------------------------------

    (
        (
            r"\bng[-\s]?ran\b.*\bamf\b.*\bprotokol",
            r"\bamf\b.*\bng[-\s]?ran\b.*\bprotokol",
            r"\bng[-\s]?ran\b.*\bamf\b.*\bprotocol",
            r"\bamf\b.*\bng[-\s]?ran\b.*\bprotocol",
        ),
        (
            "NG-RAN AMF protocol",
            "NG interface application protocol",
            "protocol between NG-RAN and AMF",
        ),
    ),

    # -----------------------------------------------------
    # REGISTRATION MANAGEMENT NETWORK FUNCTION
    # -----------------------------------------------------

    (
        (
            r"\bregistration\s+management\b.*\bnetwork\s+function",
            r"\bnetwork\s+function\b.*\bregistration\s+management",
            r"\b5gs\b.*\bregistration\s+management\b.*\bfunction",
        ),
        (
            "5GS Registration Management responsible network function",
            "network function responsible for Registration Management",
            "Registration Management functionality in 5GS",
        ),
    ),

    # -----------------------------------------------------
    # E.164 NUMBER LENGTH
    # -----------------------------------------------------

    (
        (
            r"\be\.?164\b.*\bkaç\s+basamak",
            r"\be\.?164\b.*\bmaksimum",
            r"\be\.?164\b.*\bmaximum",
            r"\be\.?164\b.*\blength",
            r"\be\.?164\b.*\bdigit",
        ),
        (
            "E.164 number maximum length",
            "maximum length of E.164 number",
            "E.164 numbering plan number length",
        ),
    ),

        # -----------------------------------------------------
    # QUIC LOSS DETECTION / RECOVERY / CONGESTION CONTROL
    # -----------------------------------------------------

    (
        (
            r"\bquic\b.*\bkayıp\b",
            r"\bquic\b.*\bloss\b",
            r"\bquic\b.*\bcongestion\b",
            r"\bquic\b.*\brecovery\b",
        ),
        (
            "QUIC loss detection and congestion control",
            "loss detection and congestion control for QUIC",
            "QUIC loss detection and recovery",
        ),
    ),

    # -----------------------------------------------------
    # NGAP DOCUMENT / SPECIFICATION
    # -----------------------------------------------------

    (
        (
            r"\bngap\b.*\b(?:standart|standard|specification)\w*",
            r"\bngap\b.*\btanımlan\w*",
        ),
        (
            "NG Application Protocol NGAP specification",
            "NGAP protocol is defined in 3GPP TS",
            "NG-RAN NG interface NG application protocol",
        ),
    ),

    # -----------------------------------------------------
    # 5G SYSTEM ARCHITECTURE DOCUMENT
    # -----------------------------------------------------

    (
        (
            r"\b5g(?:s|\s+system)?\b.*\barchitecture\b.*\b(?:standart|standard)\w*",
            r"\b5g(?:s|\s+system)?\b.*\bmimari\w*.*\b(?:standart|standard)\w*",
        ),
        (
            "System Architecture for the 5G System Stage 2",
            "Stage 2 system architecture for the 5G System",
            "present document defines the Stage 2 system architecture for the 5G System",
        ),
    ),

    # -----------------------------------------------------
    # 5G SYSTEM PROCEDURES DOCUMENT
    # -----------------------------------------------------

    (
        (
            r"\b5g(?:s|\s+system)?\b.*\bprosedür\w*.*\b(?:standart|standard)\w*",
            r"\b5g(?:s|\s+system)?\b.*\bprocedures?\b.*\b(?:standart|standard)\w*",
        ),
        (
            "Procedures for the 5G System Stage 2",
            "5G System stage 2 procedures and flows",
            "Procedures for the 5G System",
        ),
    ),

    # -----------------------------------------------------
    # QUIC + TLS
    # -----------------------------------------------------

    (
        (
            r"\bquic\b.*\btls\b",
            r"\btls\b.*\bquic\b",
        ),
        (
            "Using TLS to Secure QUIC",
            "QUIC TLS security",
            "QUIC TLS handshake",
        ),
    ),

    # -----------------------------------------------------
    # QUIC VERSION-INDEPENDENT PROPERTIES
    # -----------------------------------------------------

    (
        (
            r"\bquic\b.*\bversion-independent\b",
            r"\bquic\b.*\binvariants?\b",
        ),
        (
            "Version-Independent Properties of QUIC",
            "QUIC-INVARIANTS",
            "version-independent properties of QUIC",
        ),
    ),

    # -----------------------------------------------------
    # QPACK
    # -----------------------------------------------------

    (
        (
            r"\bqpack\b",
        ),
        (
            "QPACK Field Compression for HTTP/3",
            "QPACK",
            "QPACK field compression",
        ),
    ),

    # -----------------------------------------------------
    # WEBSOCKETS OVER HTTP/3
    # -----------------------------------------------------

    (
        (
            r"\bwebsockets?\b.*\bhttp/?3\b",
            r"\bhttp/?3\b.*\bwebsockets?\b",
        ),
        (
            "Bootstrapping WebSockets with HTTP/3",
            "WebSockets Upgrade over HTTP/3",
            "WebSockets HTTP/3",
        ),
    ),

    # -----------------------------------------------------
    # QUIC CORE RFC / SPECIFICATION
    # -----------------------------------------------------

    (
        (
            r"\bquic\b.*\brfc",
            r"\bquic\b.*\bhangi\s+standart",
            r"\bquic\b.*\bhangi\s+rfc",
            r"\bquic\b.*\bdefined\b",
            r"\bquic\b.*\btanımlan",
        ),
        (
            "QUIC version 1 core protocol",
            "core QUIC transport protocol specification",
            "document defines version 1 of QUIC",
        ),
    ),

        # -----------------------------------------------------
    # HTTP/3 RFC / SPECIFICATION
    # -----------------------------------------------------

    (
        (
            r"\bhttp/?3\b.*\brfc\b",
            r"\bhttp/?3\b.*\btanımlan\w*",
            r"\bhttp/?3\b.*\bhangi(?:\s+\w+){0,2}\s+(?:rfc|standart|doküman)",
        ),
        (
            "This document defines HTTP/3",
            "HTTP/3 RFC specification",
            "HTTP/3 Protocol Overview",
        ),
    ),

    # -----------------------------------------------------
    # HTTP/3 UNDERLYING TRANSPORT
    # -----------------------------------------------------

    (
        (
            r"\bhttp/?3\b.*\btaşıma\s+protokol",
            r"\bhttp/?3\b.*\btransport\s+protocol",
            r"\bhttp/?3\b.*\bhangi(?:\s+\w+){0,3}\s+protokol",
        ),
        (
            "HTTP/3 underlying transport protocol",
            "HTTP/3 transport layer protocol",
            "HTTP/3 protocol overview transport",
        ),
    ),
]


# =========================================================
# GENEL TELEKOM KAVRAM EŞLEŞMELERİ
# =========================================================

CONCEPT_RULES: list[
    tuple[tuple[str, ...], tuple[str, ...]]
] = [

    # -----------------------------------------------------
    # DEREGISTRATION
    # -----------------------------------------------------

    (
        (
            r"\bşebekeden(?:\s+\w+){0,4}\s+çık\w*",
            r"\bkayıttan(?:\s+\w+){0,4}\s+çık\w*",
            r"\bkayıt(?:\s+\w+){0,3}\s+sil\w*",
            r"\bderegister\w*",
            r"\bderegistration\b",
            r"\bde-registration\b",
            r"\bdetach\w*",
            r"\b5gs['’]?(?:ten|den)(?:\s+\w+){0,5}\s+ayrıl\w*",
            r"\bşebekeden(?:\s+\w+){0,5}\s+ayrıl\w*",
            r"\bnetwork(?:ten|den)?(?:\s+\w+){0,5}\s+ayrıl\w*",
        ),
        (
            "UE deregistration procedure",
            "network initiated deregistration",
            "UE initiated deregistration",
        ),
    ),

    # -----------------------------------------------------
    # REGISTRATION
    # -----------------------------------------------------

    (
        (
            r"\bşebekeye(?:\s+\w+){0,3}\s+kayıt",
            r"\bkayıt\s+ol\w*",
            r"\bregistration\s+request\b",
            r"\bregister\w*",
            r"\bregistration\b",
        ),
        (
            "5GS registration procedure",
            "Registration Request",
            "Registration Management",
        ),
    ),

    # -----------------------------------------------------
    # CONNECTION / RADIO LOSS
    # -----------------------------------------------------

    (
        (
            r"\bşebekeden(?:\s+\w+){0,4}\s+düş\w*",
            r"\bbağlantı(?:\s+\w+){0,4}\s+kop\w*",
            r"\bsinyal(?:\s+\w+){0,4}\s+git\w*",
            r"\bcoverage\s+loss\b",
            r"\bradio\s+link\s+failure\b",
        ),
        (
            "radio link failure",
            "RRC connection release",
            "loss of coverage",
        ),
    ),

    # -----------------------------------------------------
    # SERVICE REQUEST
    # -----------------------------------------------------

    (
        (
            r"\bservice\s+request\b",
            r"\bservis\s+iste\w*",
            r"\bservis\s+talep\w*",
            r"\bbağlantıyı(?:\s+\w+){0,3}\s+tekrar\s+kur\w*",
            r"\btekrar\s+aktif\w*",
            r"\bbağlantı(?:yı|yi|yu|yü)?(?:\s+\w+){0,5}\s+yeniden\s+etkinleştir\w*",
            r"\buplink\b.*\byeniden\s+etkinleştir\w*",
            r"\buplink\b.*\bservice\s+request\b",
        ),
        (
            "UE triggered Service Request",
            "Service Request procedure",
        ),
    ),

    # -----------------------------------------------------
    # PDU SESSION RELEASE
    # -----------------------------------------------------

    (
        (
            r"\bpdu\s+session.*\bkapat\w*",
            r"\bpdu\s+session.*\bsonlandır\w*",
            r"\bpdu\s+session.*\brelease\w*",
            r"\boturum.*\bkapat\w*",
            r"\boturum.*\bsonlandır\w*",
            r"\bsession.*\brelease\w*",
        ),
        (
            "PDU Session Release",
            "PDU Session Release procedure",
        ),
    ),

    # -----------------------------------------------------
    # PDU SESSION ESTABLISHMENT
    # -----------------------------------------------------

    (
        (
            r"\bpdu\s+session.*\baç\w*",
            r"\bpdu\s+session.*\bkur\w*",
            r"\bpdu\s+session.*\bestablish\w*",
            r"\boturum\s+aç\w*",
            r"\bdata\s+oturumu.*\baç\w*",
            r"\bveri\s+oturumu.*\baç\w*",
            r"\binternet\s+oturumu.*\baç\w*",
            r"\bpdu\s+session.*\boluştur\w*",
            r"\bpdu\s+session.*\bbaşlat\w*",
        ),
            (
                "PDU Session Establishment",
                "UE-requested PDU session establishment procedure",
                "UE Requested PDU Session Establishment",
            ),
),

    # -----------------------------------------------------
    # HANDOVER / MOBILITY
    # -----------------------------------------------------

    (
        (
            r"\bhandover\b",
            r"\bhücre(?:\s+\w+){0,3}\s+değiş\w*",
            r"\bbaz\s+istasyonu(?:\s+\w+){0,3}\s+değiş\w*",
            r"\bcell\s+change\b",
            r"\bmobilite\b",
        ),
        (
            "handover procedure",
            "UE mobility",
            "mobility management",
        ),
    ),

    # -----------------------------------------------------
    # 5G MULTICAST-BROADCAST SERVICES
    # -----------------------------------------------------

    (
        (
            r"\b5g\b.*\bmulticast\b.*\bbroadcast\b",
            r"\bmulticast[-\s]*broadcast\b",
            r"\bmulticast\b.*\bbroadcast\b",
            r"\b5mbs\b",
            r"\bmbs\b.*\bmimari",
            r"\bmbs\b.*\barchitecture",
        ),
        (
            (
                "architectural enhancements to the 5G system "
                "using NR to support multicast and broadcast "
                "communication services"
            ),
            "5G Multicast-Broadcast Services architecture",
            "Architecture for 5G multicast-broadcast services",
        ),
    ),

        # -----------------------------------------------------
    # CELL BROADCAST WARNING MESSAGE CANCELLATION
    # -----------------------------------------------------

    (
        (
            r"\bcell\s+broadcast\b.*\biptal\w*",
            r"\bcell\s+broadcast\b.*\bcancel\w*",
            r"\bwarning\s+message\b.*\biptal\w*",
            r"\bwarning\s+message\b.*\bcancel\w*",
            r"\buyarı\s+mesaj\w*.*\biptal\w*",
        ),
        (
            "Warning Message Cancel Procedure",
            "Stop Warning Request",
            "Cell Broadcast warning message cancellation",
        ),
    ),

    # -----------------------------------------------------
    # CELL BROADCAST
    # -----------------------------------------------------

    (
        (
            r"\bcell\s+broadcast\b",
            r"\bhücre\s+yayını\b",
            r"\bacil\s+uyarı\b",
            r"\bwarning\s+message\b",
            r"\buyarı\s+mesaj\w*",
        ),
        (
            "Cell Broadcast",
            "Public Warning System",
            "Cell Broadcast warning message",
        ),
    ),

    # -----------------------------------------------------
    # SMS
    # -----------------------------------------------------

    (
        (
            r"\bsms\b",
            r"\bkısa\s+mesaj\b",
            r"\bmesaj\s+gönder\w*",
            r"\bmesaj\s+ilet\w*",
        ),
        (
            "Short Message Service",
            "SMS procedure",
        ),
    ),

    # -----------------------------------------------------
    # AUTHENTICATION
    # -----------------------------------------------------

    (
        (
            r"\bauthentication\b",
            r"\bkimlik\s+doğrula\w*",
            r"\bdoğrulama\b",
            r"\bauthenticate\w*",
        ),
        (
            "UE authentication",
            "authentication procedure",
            "identification and authentication",
        ),
    ),

    # -----------------------------------------------------
    # NETWORK SELECTION
    # -----------------------------------------------------

    (
        (
            r"\bşebeke\s+seç\w*",
            r"\boperatör\s+seç\w*",
            r"\bnetwork\s+selection\b",
            r"\bplmn\b",
        ),
        (
            "PLMN selection",
            "network selection",
        ),
    ),

    # -----------------------------------------------------
    # ROAMING
    # -----------------------------------------------------

    (
        (
            r"\broaming\w*",
            r"\bdolaşım\w*",
            r"\byurt\s+dışında(?:\s+\w+){0,3}\s+şebeke\w*",
        ),
        (
            "roaming procedure",
            "VPLMN HPLMN roaming",
        ),
    ),

    # -----------------------------------------------------
    # EMERGENCY
    # -----------------------------------------------------

    (
        (
            r"\bacil\s+çağrı\w*",
            r"\bemergency\s+call\w*",
            r"\bacil\s+servis\w*",
        ),
        (
            "emergency call",
            "emergency services",
            "emergency registration",
        ),
    ),
]


class QueryNormalizer:
    """
    Kullanıcı sorgusuna standartlarda kullanılan
    teknik arama varyantlarını ekler.

    - Orijinal soru korunur.
    - LLM kullanılmaz.
    - Cevap sorguya eklenmez.
    - Teknik varyantlar yalnızca retrieval içindir.
    """

    def normalize(
        self,
        query: str,
        max_variants: int = 4,
    ) -> list[str]:
        clean_query = self._clean_query(
            query
        )

        if not clean_query:
            raise ValueError(
                "Sorgu boş olamaz."
            )

        if max_variants <= 0:
            raise ValueError(
                "max_variants sıfırdan büyük olmalıdır."
            )

        variants: list[str] = [
            clean_query
        ]

        query_for_matching = (
            clean_query.casefold()
        )

        # -------------------------------------------------
        # HIGH PRECISION
        # -------------------------------------------------

        high_precision_matched = (
            self._apply_rules(
                variants=variants,
                query_for_matching=query_for_matching,
                rules=HIGH_PRECISION_RULES,
                max_variants=max_variants,
            )
        )

        if high_precision_matched:
            return variants[
                :max_variants
            ]

        # -------------------------------------------------
        # CONTEXT-AWARE DEREGISTRATION
        # -------------------------------------------------

        deregistration_match = any(
            re.search(
                pattern,
                query_for_matching,
                flags=re.IGNORECASE,
            )
            for pattern in (
                r"\bşebekeden(?:\s+\w+){0,5}\s+çık\w*",
                r"\bkayıttan(?:\s+\w+){0,5}\s+çık\w*",
                r"\bkayıt(?:\s+\w+){0,4}\s+sil\w*",
                r"\bderegister",
                r"\bderegistration",
                r"\bde-registration",
                r"\bdetach",
                r"\b5gs['’]?(?:ten|den)(?:\s+\w+){0,5}\s+ayrıl\w*",
                r"\bşebekeden(?:\s+\w+){0,5}\s+ayrıl\w*",
            )
        )

        if deregistration_match:
            ue_initiated_match = any(
                re.search(
                    pattern,
                    query_for_matching,
                    flags=re.IGNORECASE,
                )
                for pattern in (
                    r"\bkendi\s+iste",
                    r"\bkendi\s+taleb",
                    r"\bkendisi\s+başlat",
                    r"\bue\s+initiated",
                    r"\bue-initiated",
                    r"\buser\s+initiated",
                    r"\bterminal\s+initiated",
                )
            )

            network_initiated_match = any(
                re.search(
                    pattern,
                    query_for_matching,
                    flags=re.IGNORECASE,
                )
                for pattern in (
                    r"\bşebeke\s+tarafından",
                    r"\bağ\s+tarafından",
                    r"\bnetwork\s+initiated",
                    r"\bnetwork-initiated",
                    r"\bnetwork\s+triggered",
                    r"\bnetwork-triggered",
                    r"\boperatör\s+tarafından",
                )
            )

            if ue_initiated_match:
                for expansion in (
                    "UE initiated deregistration",
                    "UE initiated deregistration procedure",
                    "Deregistration Request",
                ):
                    self._append_unique(
                        variants,
                        expansion,
                    )

                    if (
                        len(variants)
                        >= max_variants
                    ):
                        return variants[
                            :max_variants
                        ]

                return variants[
                    :max_variants
                ]

            if network_initiated_match:
                for expansion in (
                    "network initiated deregistration",
                    "network initiated deregistration procedure",
                    "network triggered deregistration",
                ):
                    self._append_unique(
                        variants,
                        expansion,
                    )

                    if (
                        len(variants)
                        >= max_variants
                    ):
                        return variants[
                            :max_variants
                        ]

                return variants[
                    :max_variants
                ]

        # -------------------------------------------------
        # GENEL KURALLAR
        # -------------------------------------------------

        self._apply_rules(
            variants=variants,
            query_for_matching=query_for_matching,
            rules=CONCEPT_RULES,
            max_variants=max_variants,
        )

        return variants[
            :max_variants
        ]

    def _apply_rules(
        self,
        variants: list[str],
        query_for_matching: str,
        rules: list[
            tuple[
                tuple[str, ...],
                tuple[str, ...],
            ]
        ],
        max_variants: int,
    ) -> bool:
        for patterns, expansions in rules:
            matched = any(
                re.search(
                    pattern,
                    query_for_matching,
                    flags=re.IGNORECASE,
                )
                is not None
                for pattern in patterns
            )

            if not matched:
                continue

            for expansion in expansions:
                self._append_unique(
                    variants,
                    expansion,
                )

                if (
                    len(variants)
                    >= max_variants
                ):
                    break

            return True

        return False

    @staticmethod
    def _clean_query(
        query: str,
    ) -> str:
        clean_query = (
            query
            or ""
        ).strip()

        clean_query = re.sub(
            r"\s+",
            " ",
            clean_query,
        )

        return clean_query

    @staticmethod
    def _append_unique(
        variants: list[str],
        value: str,
    ) -> None:
        clean_value = (
            value
            or ""
        ).strip()

        if not clean_value:
            return

        normalized_value = (
            clean_value.casefold()
        )

        existing = {
            item.strip().casefold()
            for item in variants
        }

        if normalized_value in existing:
            return

        variants.append(
            clean_value
        )