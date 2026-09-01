import {
  useState,
} from "react"

import type {
  Source,
} from "../services/chatApi"

import SourceCard from "./SourceCard"
import SourceClauseViewer from "./SourceClauseViewer"

type SourcesPanelProps = {
  sources: Source[]
  onClose: () => void
}

function SourcesPanel({
  sources,
  onClose,
}: SourcesPanelProps) {
  const [
    selectedSource,
    setSelectedSource,
  ] = useState<Source | null>(null)

  const uniqueSources = Array.from(
    new Map(
      sources.map((source) => [
        [
          source.org,
          source.code,
          source.version,
          source.clause,
          source.version_id,
          source.clause_id,
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
        aria-label={
          "Kaynak panelini kapat"
        }
        onClick={onClose}
      />

      <aside
        id="sources-panel"
        className="sources-panel"
        aria-label={
          "Sohbette kullan\u0131lan kaynaklar"
        }
      >
        <header className="sources-panel-header">
          <div>
            <h2>
              {selectedSource
                ? "Kaynak maddesi"
                : "Sohbet kaynaklar\u0131"}
            </h2>

            <p>
              {selectedSource
                ? "Yan\u0131t\u0131n dayand\u0131\u011f\u0131 kesin standart maddesi."
                : "Bu konu\u015fmada yan\u0131tlara dayanak olarak kullan\u0131lan dok\u00fcmanlar."}
            </p>
          </div>

          <button
            type="button"
            className="sources-panel-close"
            aria-label={
              "Kaynak panelini kapat"
            }
            onClick={onClose}
          >
            {"\u00d7"}
          </button>
        </header>

        <div className="sources-panel-content">
          {selectedSource ? (
            <SourceClauseViewer
              source={selectedSource}
              onBack={() =>
                setSelectedSource(null)
              }
            />
          ) : uniqueSources.length === 0 ? (
            <div className="sources-empty-state">
              <div className="sources-empty-icon">
                P
              </div>

              <h3>
                {"Hen\u00fcz kaynak bulunmuyor"}
              </h3>

              <p>
                {"Backend bir yan\u0131tta kaynak d\u00f6nd\u00fcrd\u00fc\u011f\u00fcnde ilgili standartlar burada listelenecek."}
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
                      source.version_id,
                      source.clause_id,
                      source.source_url,
                    ].join("|")}
                    source={source}
                    onViewClause={
                      setSelectedSource
                    }
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
