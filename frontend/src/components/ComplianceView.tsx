import {
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react"

import {
  compareCompliance,
  type ComplianceResponse,
} from "../services/chatApi"

type ComplianceViewProps = {
  onBack: () => void
}

const ACCEPTED_FILE_TYPES =
  ".xlsx,.xls,.csv,.pdf,.docx,.pptx,.txt,.md,.json,.xml,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"

function statusLabel(
  status: string,
): string {
  switch (status) {
    case "FC":
      return "Tam Kar\u015f\u0131lan\u0131yor"

    case "PC":
      return "K\u0131smen Kar\u015f\u0131lan\u0131yor"

    case "NC":
      return "Kar\u015f\u0131lanm\u0131yor"

    default:
      return "\u0130nceleme Gerekli"
  }
}

function fileKey(
  file: File,
): string {
  return [
    file.name,
    file.size,
    file.lastModified,
  ].join("::")
}

function mergeFiles(
  currentFiles: File[],
  incomingFiles: File[],
): File[] {
  const knownKeys = new Set(
    currentFiles.map(
      fileKey,
    ),
  )

  const merged = [
    ...currentFiles,
  ]

  for (const file of incomingFiles) {
    const key = fileKey(
      file,
    )

    if (knownKeys.has(key)) {
      continue
    }

    knownKeys.add(key)
    merged.push(file)
  }

  return merged
}

function formatFileSize(
  size: number,
): string {
  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(
      size / 1024
    ).toFixed(1)} KB`
  }

  return `${(
    size / (1024 * 1024)
  ).toFixed(1)} MB`
}


const COMPLIANCE_SIGNAL_LABELS: Record<
  string,
  string
> = {
  x86: "Standart x86 sunucu deste?i",
  vmware: "VMware platform deste?i",
  nutanix: "Nutanix platform deste?i",

  active_active: "Aktif-Aktif mimari",
  active_standby: "Aktif-Standby mimari",
  geo_redundancy: "Co?rafi yedeklilik",
  availability: "Sistem kullan?labilirli?i",
  scalability: "?l?eklenebilirlik",
  replication: "Replikasyon",
  backup: "Yedekleme",

  ipv6: "IPv6 deste?i",
  http2: "HTTP/2 deste?i",

  tls: "TLS deste?i",
  tls_12: "TLS 1.2 deste?i",
  tls_13: "TLS 1.3 deste?i",
  https: "HTTPS deste?i",
  mutual_tls: "Kar??l?kl? TLS (mTLS)",

  aes_256: "AES-256 ?ifreleme",
  two_factor_authentication:
    "?ift fakt?rl? kimlik do?rulama",

  rbac: "Rol tabanl? eri?im kontrol? (RBAC)",
  account_lockout: "Hesap kilitleme",
  ldap: "LDAP entegrasyonu",
  active_directory: "Active Directory entegrasyonu",
  central_directory: "Merkezi dizin entegrasyonu",

  syslog: "Syslog deste?i",
  siem_integration: "SIEM entegrasyonu",
  rest_api: "REST API deste?i",
}


function complianceSignalLabel(
  signal: string,
): string {
  const clean = (
    signal
    || ""
  ).trim()

  if (!clean) {
    return ""
  }

  const known = (
    COMPLIANCE_SIGNAL_LABELS[
      clean
    ]
  )

  if (known) {
    return known
  }

  return clean
    .replaceAll(
      "_",
      " ",
    )
    .replace(
      /\b\w/g,
      (value) =>
        value.toUpperCase(),
    )
}


function complianceGapSignals(
  status: string,
  missingSignals: string[] = [],
  notSupportedSignals: string[] = [],
  reviewSignals: string[] = [],
): string[] {
  const raw = (
    status === "NC"
      ? [
          ...notSupportedSignals,
          ...missingSignals,
        ]
      : [
          ...reviewSignals,
          ...missingSignals,
        ]
  )

  return Array.from(
    new Set(
      raw
        .map(
          complianceSignalLabel,
        )
        .filter(Boolean),
    ),
  )
}



function normalizeComplianceText(
  value: string,
): string {
  return (value || "")
    .normalize("NFKD")
    .replace(
      /[\u0300-\u036f]/g,
      "",
    )
    .replaceAll("\u0131", "i")
    .replaceAll("\u015f", "s")
    .replaceAll("\u015e", "s")
    .replaceAll("\u00e7", "c")
    .replaceAll("\u00c7", "c")
    .replaceAll("\u011f", "g")
    .replaceAll("\u011e", "g")
    .replaceAll("\u00fc", "u")
    .replaceAll("\u00dc", "u")
    .replaceAll("\u00f6", "o")
    .replaceAll("\u00d6", "o")
    .toLowerCase()
}


function complianceGapReason(
  status: string,
  requirement: string,
  missingSignals: string[] = [],
  notSupportedSignals: string[] = [],
): string {
  const normalized = (
    normalizeComplianceText(
      requirement,
    )
  )

  const evidenceRequirement = (
    normalized.includes("referans")
    || normalized.includes("tedarikci")
    || normalized.includes("uretici")
    || normalized.includes("ticari kurulum")
    || normalized.includes("liste sun")
    || normalized.includes("dokuman")
    || normalized.includes("belge")
    || normalized.includes("sertifika")
  )

  if (
    status === "REVIEW"
    && evidenceRequirement
  ) {
    return (
      "Bu madde yaln\u0131zca bir \u00fcr\u00fcn "
      + "\u00f6zelli\u011fi istemiyor; referans, "
      + "tedarik\u00e7i, kurulum veya do\u011frulay\u0131c\u0131 "
      + "kan\u0131t talep ediyor. Y\u00fcklenen \u015firket "
      + "\u00f6zellik dosyalar\u0131nda bu bilgiler "
      + "yeterli de\u011fil."
    )
  }

  if (
    status === "NC"
    && notSupportedSignals.length > 0
  ) {
    return (
      "\u015eirket \u00f6zelliklerinde bu maddeyle "
      + "ilgili bir veya daha fazla teknik yetenek "
      + "a\u00e7\u0131k\u00e7a desteklenmiyor."
    )
  }

  if (
    status === "NC"
    && missingSignals.length > 0
  ) {
    return (
      "\u015eartnamenin istedi\u011fi teknik "
      + "yeteneklerin tamam\u0131 \u015firket "
      + "\u00f6zelliklerinde bulunamad\u0131."
    )
  }

  if (status === "NC") {
    return (
      "Y\u00fcklenen \u015firket \u00f6zellik "
      + "dosyalar\u0131nda bu gereksinimi "
      + "do\u011frulayan yeterli yetenek veya "
      + "kan\u0131t bulunamad\u0131."
    )
  }

  return (
    "Mevcut \u015firket bilgilerinden bu madde "
    + "i\u00e7in kesin bir uygunluk karar\u0131 "
    + "\u00fcretilemiyor; ek do\u011frulama gerekiyor."
  )
}


function complianceRequirementActions(
  requirement: string,
): string[] {
  const normalized = (
    normalizeComplianceText(
      requirement,
    )
  )

  const actions: string[] = []

  if (
    normalized.includes("x86")
    && (
      normalized.includes(
        "donanim uretici",
      )
      || normalized.includes(
        "farkli uretici",
      )
    )
  ) {
    actions.push(
      "Donan\u0131m \u00fcreticisinden ba\u011f\u0131ms\u0131z standart x86 sunucu kurulum deste\u011fi",
    )
  }

  if (
    normalized.includes("vmware")
    || normalized.includes("nutanix")
  ) {
    actions.push(
      "VMware / Nutanix gibi sanalla\u015ft\u0131rma platformlar\u0131nda kurulum deste\u011fi",
    )
  }

  if (
    normalized.includes("referans listesi")
  ) {
    actions.push(
      "Gerekli entegrasyonlar\u0131 ve \u00fc\u00e7\u00fcnc\u00fc taraf \u00fcretici / tedarik\u00e7ileri g\u00f6steren referans listesi",
    )
  }

  if (
    normalized.includes("aktif abone")
  ) {
    actions.push(
      "\u015eartnamede istenen minimum aktif abone kapasitesini kar\u015f\u0131layan operat\u00f6r referans\u0131",
    )
  }

  if (
    normalized.includes("ticari kurulum")
  ) {
    actions.push(
      "\u015eartnamede istenen minimum ticari kurulum say\u0131s\u0131n\u0131 do\u011frulayan referans / kan\u0131t",
    )
  }

  if (
    normalized.includes("web")
    && normalized.includes("gui")
  ) {
    actions.push(
      "Web tabanl\u0131 grafik kullan\u0131c\u0131 aray\u00fcz\u00fc (GUI) deste\u011fi",
    )
  }

  if (
    normalized.includes("ipv6")
  ) {
    actions.push(
      "IPv6 deste\u011fi",
    )
  }

  if (
    normalized.includes("http/2")
    || normalized.includes("http2")
  ) {
    actions.push(
      "HTTP/2 deste\u011fi",
    )
  }

  if (
    normalized.includes("aktif-aktif")
    || normalized.includes("aktif aktif")
  ) {
    actions.push(
      "Aktif-Aktif mimari deste\u011fi",
    )
  }

  return Array.from(
    new Set(actions),
  )
}


function complianceGapItems(
  requirement: string,
  status: string,
  missingSignals: string[] = [],
  notSupportedSignals: string[] = [],
  reviewSignals: string[] = [],
): string[] {
  const signalItems = (
    complianceGapSignals(
      status,
      missingSignals,
      notSupportedSignals,
      reviewSignals,
    )
  )

  if (signalItems.length > 0) {
    return signalItems
  }

  const requirementItems = (
    complianceRequirementActions(
      requirement,
    )
  )

  if (requirementItems.length > 0) {
    return requirementItems
  }

  return [
    status === "NC"
      ? (
        "Bu gereksinimi kar\u015f\u0131layan teknik "
        + "yetenek veya do\u011frulay\u0131c\u0131 kan\u0131t"
      )
      : (
        "Bu gereksinimin kar\u015f\u0131lan\u0131p "
        + "kar\u015f\u0131lanmad\u0131\u011f\u0131n\u0131 "
        + "g\u00f6steren a\u00e7\u0131k \u015firket bilgisi"
      ),
  ]
}


function ComplianceView({
  onBack,
}: ComplianceViewProps) {
  const [
    companyFiles,
    setCompanyFiles,
  ] = useState<File[]>([])

  const [
    specificationFiles,
    setSpecificationFiles,
  ] = useState<File[]>([])

  const [
    result,
    setResult,
  ] = useState<ComplianceResponse | null>(null)

  const [
    isLoading,
    setIsLoading,
  ] = useState(false)

  const [
    error,
    setError,
  ] = useState("")

  function handleCompanyFiles(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const selected = Array.from(
      event.target.files ?? [],
    )

    setCompanyFiles(
      (current) =>
        mergeFiles(
          current,
          selected,
        ),
    )

    event.target.value = ""
  }

  function handleSpecificationFiles(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const selected = Array.from(
      event.target.files ?? [],
    )

    setSpecificationFiles(
      (current) =>
        mergeFiles(
          current,
          selected,
        ),
    )

    event.target.value = ""
  }

  function removeCompanyFile(
    targetFile: File,
  ) {
    const key = fileKey(
      targetFile,
    )

    setCompanyFiles(
      (current) =>
        current.filter(
          (file) =>
            fileKey(file) !== key,
        ),
    )
  }

  function removeSpecificationFile(
    targetFile: File,
  ) {
    const key = fileKey(
      targetFile,
    )

    setSpecificationFiles(
      (current) =>
        current.filter(
          (file) =>
            fileKey(file) !== key,
        ),
    )
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    if (
      companyFiles.length === 0
      || specificationFiles.length === 0
    ) {
      setError(
        "Her iki tarafa da en az bir dosya eklemelisiniz.",
      )
      return
    }

    setError("")
    setResult(null)
    setIsLoading(true)

    try {
      const response =
        await compareCompliance(
          companyFiles,
          specificationFiles,
        )

      setResult(response)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Kar\u015f\u0131la\u015ft\u0131rma ba\u015far\u0131s\u0131z oldu.",
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section className="compliance-view">
      <div className="workspace-toolbar">
        <div>
          <strong>
            {"\u015eartname Kar\u015f\u0131la\u015ft\u0131rma"}
          </strong>

          <span>
            {" \u00b7 FC / PC / NC / \u0130nceleme"}
          </span>
        </div>

        <button
          type="button"
          className="workspace-change-button"
          onClick={onBack}
        >
          {"Modu De\u011fi\u015ftir"}
        </button>
      </div>

      <div className="compliance-intro">
        <h2>
          {"Teknik \u015fartname uygunluk analizi"}
        </h2>

        <p>
          {
            "Paradoks, kar\u015f\u0131 taraf\u0131n teknik gereksinimlerini "
            + "\u015firketinizin mevcut \u00f6zellik ve yetenekleriyle "
            + "kar\u015f\u0131la\u015ft\u0131r\u0131r. Her iki tarafa da "
            + "birden fazla dosya ekleyebilirsiniz."
          }
        </p>
      </div>

      <form
        className="compliance-upload-form"
        onSubmit={handleSubmit}
      >
        <div className="compliance-upload-grid">
          <div
            className={[
              "compliance-upload-card",
              companyFiles.length > 0
                ? "has-file"
                : "",
            ].join(" ")}
          >
            <div className="upload-card-top">
              <span className="upload-step">
                01
              </span>

              {companyFiles.length > 0 && (
                <span className="upload-ready">
                  {"\u2713 "}
                  {companyFiles.length}
                  {" dosya"}
                </span>
              )}
            </div>

            <div className="upload-card-icon">
              {"\u2191"}
            </div>

            <div className="upload-card-content">
              <strong>
                {"Bizim \u00d6zelliklerimiz"}
              </strong>

              <p>
                {
                  "Mevcut sistem, \u00fcr\u00fcn, \u00f6zellik ve "
                  + "yeteneklerinizi i\u00e7eren dosyalar\u0131 ekleyin."
                }
              </p>
            </div>

            <label
              className="upload-select-button"
              htmlFor="company-files"
            >
              {"+ Dosya Ekle"}
            </label>

            <input
              id="company-files"
              className="compliance-file-input"
              type="file"
              multiple
              accept={ACCEPTED_FILE_TYPES}
              onChange={handleCompanyFiles}
            />

            <small className="upload-formats">
              {
                "XLSX \u00b7 XLS \u00b7 CSV \u00b7 PDF \u00b7 DOCX \u00b7 "
                + "PPTX \u00b7 TXT \u00b7 MD \u00b7 JSON \u00b7 XML \u00b7 "
                + "PNG \u00b7 JPG \u00b7 WEBP \u00b7 TIFF"
              }
            </small>

            {companyFiles.length > 0 && (
              <div className="selected-file-list">
                {companyFiles.map(
                  (file) => (
                    <div
                      className="selected-file-row"
                      key={fileKey(file)}
                    >
                      <span
                        className="selected-file-icon"
                        aria-hidden="true"
                      >
                        {"\u2713"}
                      </span>

                      <div className="selected-file-info">
                        <strong>
                          {file.name}
                        </strong>

                        <small>
                          {formatFileSize(
                            file.size,
                          )}
                        </small>
                      </div>

                      <button
                        type="button"
                        className="selected-file-remove"
                        aria-label={
                          `${file.name} dosyas\u0131n\u0131 kald\u0131r`
                        }
                        title={
                          "Dosyay\u0131 kald\u0131r"
                        }
                        onClick={() =>
                          removeCompanyFile(
                            file,
                          )
                        }
                      >
                        {"\u00d7"}
                      </button>
                    </div>
                  ),
                )}
              </div>
            )}
          </div>

          <div
            className="compliance-transfer-indicator"
            aria-hidden="true"
          >
            {"\u2194"}
          </div>

          <div
            className={[
              "compliance-upload-card",
              specificationFiles.length > 0
                ? "has-file"
                : "",
            ].join(" ")}
          >
            <div className="upload-card-top">
              <span className="upload-step">
                02
              </span>

              {specificationFiles.length > 0 && (
                <span className="upload-ready">
                  {"\u2713 "}
                  {specificationFiles.length}
                  {" dosya"}
                </span>
              )}
            </div>

            <div className="upload-card-icon">
              {"\u2191"}
            </div>

            <div className="upload-card-content">
              <strong>
                {"Firma \u015eartnamesi"}
              </strong>

              <p>
                {
                  "Kar\u015f\u0131la\u015ft\u0131r\u0131lacak teknik "
                  + "\u015fartname, ek dok\u00fcman ve gereksinim "
                  + "dosyalar\u0131n\u0131 ekleyin."
                }
              </p>
            </div>

            <label
              className="upload-select-button"
              htmlFor="specification-files"
            >
              {"+ Dosya Ekle"}
            </label>

            <input
              id="specification-files"
              className="compliance-file-input"
              type="file"
              multiple
              accept={ACCEPTED_FILE_TYPES}
              onChange={
                handleSpecificationFiles
              }
            />

            <small className="upload-formats">
              {
                "XLSX \u00b7 XLS \u00b7 CSV \u00b7 PDF \u00b7 DOCX \u00b7 "
                + "PPTX \u00b7 TXT \u00b7 MD \u00b7 JSON \u00b7 XML \u00b7 "
                + "PNG \u00b7 JPG \u00b7 WEBP \u00b7 TIFF"
              }
            </small>

            {specificationFiles.length > 0 && (
              <div className="selected-file-list">
                {specificationFiles.map(
                  (file) => (
                    <div
                      className="selected-file-row"
                      key={fileKey(file)}
                    >
                      <span
                        className="selected-file-icon"
                        aria-hidden="true"
                      >
                        {"\u2713"}
                      </span>

                      <div className="selected-file-info">
                        <strong>
                          {file.name}
                        </strong>

                        <small>
                          {formatFileSize(
                            file.size,
                          )}
                        </small>
                      </div>

                      <button
                        type="button"
                        className="selected-file-remove"
                        aria-label={
                          `${file.name} dosyas\u0131n\u0131 kald\u0131r`
                        }
                        title={
                          "Dosyay\u0131 kald\u0131r"
                        }
                        onClick={() =>
                          removeSpecificationFile(
                            file,
                          )
                        }
                      >
                        {"\u00d7"}
                      </button>
                    </div>
                  ),
                )}
              </div>
            )}
          </div>
        </div>

        <button
          type="submit"
          className="compare-button compliance-primary-action"
          disabled={
            isLoading
            || companyFiles.length === 0
            || specificationFiles.length === 0
          }
        >
          {isLoading
            ? "Kar\u015f\u0131la\u015ft\u0131r\u0131l\u0131yor..."
            : (
              <>
                <span>
                  {"Kar\u015f\u0131la\u015ft\u0131r"}
                </span>

                <span aria-hidden="true">
                  {"\u2192"}
                </span>
              </>
            )}
        </button>
      </form>

      {error && (
        <div className="compliance-error">
          {error}
        </div>
      )}

      {result && (
        <>
          <div className="compliance-summary-grid">
            <div>
              <strong>
                {result.summary.total_requirements}
              </strong>
              <span>
                {"Toplam Madde"}
              </span>
            </div>

            <div>
              <strong>
                {result.summary.fully_compliant}
              </strong>
              <span>
                {"Tam Kar\u015f\u0131lan\u0131yor"}
              </span>
            </div>

            <div>
              <strong>
                {result.summary.partially_compliant}
              </strong>
              <span>
                {"K\u0131smen Kar\u015f\u0131lan\u0131yor"}
              </span>
            </div>

            <div>
              <strong>
                {result.summary.non_compliant}
              </strong>
              <span>
                {"Kar\u015f\u0131lanm\u0131yor"}
              </span>
            </div>

            <div>
              <strong>
                {result.summary.manual_review}
              </strong>
              <span>
                {"\u0130nceleme Gerekli"}
              </span>
            </div>

            <div>
              <strong>
                {result.summary.coverage_percent}%
              </strong>
              <span>
                {"Uygunluk"}
              </span>
            </div>
          </div>

          <div className="compliance-table-wrapper">
            <table className="compliance-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>
                    {"\u015eartname Maddesi"}
                  </th>
                  <th>Durum</th>
                  <th>
                    {"Dayanak / Bizim \u00d6zelli\u011fimiz"}
                  </th>
                  <th>
                    {"A\u00e7\u0131klama"}
                  </th>
                </tr>
              </thead>

              <tbody>
                {result.results.map(
                  (item) => (
                    <tr
                      key={
                        item.requirement_index
                      }
                    >
                      <td>
                        {item.requirement_index}
                      </td>

                      <td>
                        <div>
                          {item.requirement}
                        </div>

                        {item.specification_source_filename && (
                          <div className="compliance-requirement-meta">
                            <span>
                              {
                                item.specification_source_filename
                              }
                            </span>

                            {item.specification_source_page !== null && (
                              <span>
                                {
                                  "Sayfa "
                                  + item.specification_source_page
                                }
                              </span>
                            )}
                          </div>
                        )}
                      </td>

                      <td>
                        <span
                          className={
                            `compliance-status status-${item.status.toLowerCase()}`
                          }
                        >
                          {statusLabel(
                            item.status,
                          )}
                        </span>
                      </td>

                        <td>
                          {item.evidence
                            ? (
                              <>
                                <div>
                                  {item.evidence.text}
                                </div>

                                <div className="compliance-evidence-meta">
                                  <span>
                                    {
                                      item.evidence.source_filename
                                      || "Kaynak dosya bilinmiyor"
                                    }
                                  </span>

                                  {item.evidence.source_page !== null && (
                                    <span>
                                      {
                                        "Sayfa "
                                        + item.evidence.source_page
                                      }
                                    </span>
                                  )}
                                </div>

                                <small>
                                  {"Benzerlik: "}
                                  {item.evidence.score}
                                </small>
                              </>
                            )
                            : (
                              <div
                                className={
                                  `compliance-no-evidence no-evidence-${item.status.toLowerCase()}`
                                }
                              >
                                <strong>
                                  {
                                    item.status === "NC"
                                      ? "Do\u011frulanabilir kar\u015f\u0131l\u0131k bulunamad\u0131"
                                      : "Manuel do\u011frulama gerekiyor"
                                  }
                                </strong>

                                <div className="compliance-gap-content">
                                  <div className="compliance-gap-reason">
                                    <span className="compliance-gap-title">
                                      {"Neden?"}
                                    </span>

                                    <span>
                                      {complianceGapReason(
                                        item.status,
                                        item.requirement,
                                        item.missing_signals,
                                        item.not_supported_signals,
                                      )}
                                    </span>
                                  </div>

                                  <div>
                                    <span className="compliance-gap-title">
                                      {
                                        item.status === "NC"
                                          ? "Edinilmesi / tamamlanmas\u0131 gerekenler"
                                          : "Do\u011frulanmas\u0131 / haz\u0131rlanmas\u0131 gerekenler"
                                      }
                                    </span>

                                    <ul className="compliance-gap-list">
                                      {complianceGapItems(
                                        item.requirement,
                                        item.status,
                                        item.missing_signals,
                                        item.not_supported_signals,
                                        item.review_signals,
                                      ).map(
                                        (gapItem) => (
                                          <li key={gapItem}>
                                            {gapItem}
                                          </li>
                                        ),
                                      )}
                                    </ul>
                                  </div>

                                  <small className="compliance-gap-action">
                                    {
                                      item.status === "NC"
                                        ? (
                                          "Bu yetenek zaten mevcutsa \u015firket "
                                          + "\u00f6zellik dosyas\u0131na a\u00e7\u0131k\u00e7a ekleyin; "
                                          + "mevcut de\u011filse edinim veya geli\u015ftirme "
                                          + "plan\u0131na al\u0131n."
                                        )
                                        : (
                                          "Gerekli bilgi veya kan\u0131t topland\u0131ktan "
                                          + "sonra \u015firket \u00f6zellik dosyas\u0131na "
                                          + "a\u00e7\u0131k ve do\u011frulanabilir bi\u00e7imde eklenmeli."
                                        )
                                    }
                                  </small>
                                </div>
                              </div>
                            )}
                        </td>

                      <td>
                        {item.explanation}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>

          <section className="extra-capabilities">
            <h3>
              {"Bizde Bulunan Ek / Fazla \u00d6zellikler"}
            </h3>

            {result.extra_capabilities.length === 0 ? (
              <p>
                {"Ek \u00f6zellik tespit edilmedi."}
              </p>
            ) : (
              <ul>
                {result.extra_capabilities.map(
                  (item) => (
                    <li
                      key={
                        `${item.company_row}-${item.capability}`
                      }
                    >
                      {item.capability}
                    </li>
                  ),
                )}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  )
}

export default ComplianceView
