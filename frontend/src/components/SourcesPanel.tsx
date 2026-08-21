import type { Source } from "../services/chatApi"
import SourceCard from "./SourceCard"

type SourcesPanelProps = {
  sources: Source[]
  onClose: () => void
}

function SourcesPanel({
  sources,
  onClose,
}: SourcesPanelProps) {
  const uniqueSources = Array.from(
    new Map(
      sources.map((source) => [
        [
          source.org,
          source.code,
          source.version,
          source.clause,
          source.source_url,
        ].join("|"),
        source,
      ]),
    ).values(),
  )

  return (
    <>
      <button
        type="button"
        className="sources-panel-backdrop"
        aria-label="Kaynak panelini kapat"
        onClick={onClose}
      />

      <aside
        id="sources-panel"
        className="sources-panel"
        aria-label="Sohbette kullanılan kaynaklar"
      >
        <header className="sources-panel-header">
          <div>
            <h2>Sohbet kaynakları</h2>

            <p>
              Bu konuşmada yanıtlara dayanak olarak
              kullanılan dokümanlar.
            </p>
          </div>

          <button
            type="button"
            className="sources-panel-close"
            aria-label="Kaynak panelini kapat"
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <div className="sources-panel-content">
          {uniqueSources.length === 0 ? (
            <div className="sources-empty-state">
              <div className="sources-empty-icon">
                P
              </div>

              <h3>
                Henüz kaynak bulunmuyor
              </h3>

              <p>
                Backend bir yanıtta kaynak
                döndürdüğünde ilgili standartlar
                burada listelenecek.
              </p>
            </div>
          ) : (
            <div className="sources-panel-list">
              {uniqueSources.map(
                (source) => (
                  <SourceCard
                    key={[
                      source.org,
                      source.code,
                      source.version,
                      source.clause,
                      source.source_url,
                    ].join("|")}
                    source={source}
                  />
                ),
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

export default SourcesPanel