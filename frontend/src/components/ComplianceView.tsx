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
              <span>FC</span>
            </div>

            <div>
              <strong>
                {result.summary.partially_compliant}
              </strong>
              <span>PC</span>
            </div>

            <div>
              <strong>
                {result.summary.non_compliant}
              </strong>
              <span>NC</span>
            </div>

            <div>
              <strong>
                {result.summary.manual_review}
              </strong>
              <span>
                {"\u0130nceleme"}
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
                          : "\u2014"}
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
