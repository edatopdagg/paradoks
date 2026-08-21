import type { Source } from "../services/chatApi"
import SourceCard from "./SourceCard"

type SourcesViewProps = {
  sources: Source[]
}

function SourcesView({
  sources,
}: SourcesViewProps) {
  return (
    <section className="workspace-view">
      <div className="workspace-view-header">
        <div>
          <span className="workspace-eyebrow">
            Doküman yönetimi
          </span>

          <h2>Kaynaklar</h2>

          <p>
            Sisteme aktarılan telekom standartları,
            sürümleri ve erişim durumları bu bölümde
            görüntülenecek.
          </p>
        </div>
      </div>

      {sources.length === 0 ? (
        <div className="workspace-empty-state">
          <div className="workspace-empty-icon">
            P
          </div>

          <h3>Henüz görüntülenecek kaynak yok</h3>

          <p>
            Veritabanı entegrasyonu tamamlandığında
            standart dokümanları, maddeleri ve kaynak
            bağlantıları burada listelenecek.
          </p>
        </div>
      ) : (
        <div className="workspace-source-grid">
          {sources.map((source, index) => (
            <SourceCard
              key={[
                source.org,
                source.code,
                source.version,
                source.clause,
                index,
              ].join("-")}
              source={source}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default SourcesView