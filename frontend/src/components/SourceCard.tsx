import type { Source } from "../services/chatApi"

type SourceCardProps = {
  source: Source
}

function SourceCard({
  source,
}: SourceCardProps) {
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
          Sürüm: {source.version}
        </span>

        <span>
          Madde: {source.clause}
        </span>

        {source.clause_title && (
          <span>
            Başlık: {source.clause_title}
          </span>
        )}
      </div>

      {source.source_url && (
        <a
          href={source.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Kaynağı görüntüle
        </a>
      )}
    </article>
  )
}

export default SourceCard