import type { Source } from "../services/chatApi"

type SourceCardProps = {
  source: Source
  onViewClause?: (source: Source) => void
}

function SourceCard({
  source,
  onViewClause,
}: SourceCardProps) {
  const hasExactLocation = Boolean(
    source.version_id &&
    source.clause_id,
  )

  return (
    <article className="message-source-card">
      <div className="source-card-header">
        <strong>
          {source.org} {source.code}
        </strong>

        <span>{source.status}</span>
      </div>

      <div className="source-card-details">
        <span>
          {"S\u00fcr\u00fcm: "}{source.version}
        </span>

        <span>
          {"Madde: "}{source.clause}
        </span>

        {source.clause_title && (
          <span>
            {"Ba\u015fl\u0131k: "}
            {source.clause_title}
          </span>
        )}
      </div>

      <div className="source-card-actions">
        {hasExactLocation && onViewClause && (
          <button
            type="button"
            className="exact-source-button"
            onClick={() => onViewClause(source)}
          >
            {"Maddeyi g\u00f6r\u00fcnt\u00fcle"}
          </button>
        )}

        {!hasExactLocation &&
          source.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noreferrer"
            >
              {"Resm\u00ee kayna\u011f\u0131 a\u00e7"}
            </a>
          )}
      </div>
    </article>
  )
}

export default SourceCard
