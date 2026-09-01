import {
  useEffect,
  useState,
} from "react"

import {
  fetchSourceClause,
} from "../services/chatApi"

import type {
  Source,
  SourceClause,
} from "../services/chatApi"

type SourceClauseViewerProps = {
  source: Source
  onBack: () => void
}

function SourceClauseViewer({
  source,
  onBack,
}: SourceClauseViewerProps) {
  const [
    clause,
    setClause,
  ] = useState<SourceClause | null>(null)

  const [
    errorMessage,
    setErrorMessage,
  ] = useState("")

  const [
    isLoading,
    setIsLoading,
  ] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    async function loadClause() {
      if (
        !source.version_id ||
        !source.clause_id
      ) {
        setErrorMessage(
          "Bu kaynak i\u00e7in kesin madde konumu bulunmuyor.",
        )
        setIsLoading(false)
        return
      }

      try {
        const result = await fetchSourceClause(
          source.version_id,
          source.clause_id,
          controller.signal,
        )

        setClause(result)
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return
        }

        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Kaynak maddesi y\u00fcklenemedi.",
        )
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      }
    }

    void loadClause()

    return () => {
      controller.abort()
    }
  }, [
    source.version_id,
    source.clause_id,
  ])

  return (
    <section className="source-clause-viewer">
      <button
        type="button"
        className="source-clause-back"
        onClick={onBack}
      >
        {"\u2190 Kaynak listesine d\u00f6n"}
      </button>

      {isLoading && (
        <div
          className="source-clause-message"
          role="status"
        >
          {"Kaynak maddesi y\u00fckleniyor..."}
        </div>
      )}

      {!isLoading && errorMessage && (
        <div
          className="source-clause-error"
          role="alert"
        >
          <strong>
            {"Kaynak a\u00e7\u0131lamad\u0131"}
          </strong>

          <p>{errorMessage}</p>

          {source.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noreferrer"
            >
              {"Resm\u00ee dok\u00fcman\u0131 a\u00e7"}
            </a>
          )}
        </div>
      )}

      {!isLoading && clause && (
        <article className="source-clause-document">
          <header>
            <span className="source-clause-identity">
              {clause.org} {clause.code}
            </span>

            <h3>
              {clause.clause}.{" "}
              {clause.clause_title}
            </h3>

            <div className="source-clause-meta">
              <span>
                {"S\u00fcr\u00fcm: "}
                {clause.version}
              </span>

              {clause.page_start != null && (
                <span>
                  {"Sayfa: "}
                  {clause.page_start}
                  {clause.page_end != null &&
                    clause.page_end !==
                      clause.page_start &&
                    `-${clause.page_end}`}
                </span>
              )}
            </div>
          </header>

          <div className="source-clause-body">
            {clause.body_text}
          </div>

          {clause.source_url && (
            <footer>
              <a
                href={clause.source_url}
                target="_blank"
                rel="noreferrer"
              >
                {"Resm\u00ee dok\u00fcman\u0131 yeni sekmede a\u00e7"}
              </a>
            </footer>
          )}
        </article>
      )}
    </section>
  )
}

export default SourceClauseViewer
