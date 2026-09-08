type WorkspaceMode =
  | "telecom"
  | "radio"
  | "compliance"

type ModeSelectorProps = {
  onSelect: (mode: WorkspaceMode) => void
}

function ModeSelector({
  onSelect,
}: ModeSelectorProps) {
  return (
    <section className="mode-selector">
      <div className="welcome-icon">P</div>

      <h2>
        {"Hangi alanda i\u015flem yapmak istiyorsunuz?"}
      </h2>

      <p className="mode-selector-subtitle">
        {"Paradoks arama alan\u0131n\u0131 se\u00e7iminize g\u00f6re s\u0131n\u0131rland\u0131r\u0131r."}
      </p>

      <div className="mode-grid">
        <button
          type="button"
          className="mode-card"
          onClick={() => onSelect("telecom")}
        >
          <strong>
            {"Telekom Standartlar\u0131"}
          </strong>

          <span>
            {"3GPP, ATIS, Nokia, ETSI GSM ve ili\u015fkili telekom dok\u00fcmanlar\u0131"}
          </span>
        </button>

        <button
          type="button"
          className="mode-card"
          onClick={() => onSelect("radio")}
        >
          <strong>
            {"Radyo Sistemleri"}
          </strong>

          <span>
            {"DAB/DAB+, DVB-T2, FM, RDS ve RBDS kaynaklar\u0131"}
          </span>
        </button>

        <button
          type="button"
          className="mode-card mode-card-wide"
          onClick={() => onSelect("compliance")}
        >
          <strong>
            {"\u015eartname Kar\u015f\u0131la\u015ft\u0131rma"}
          </strong>

          <span>
            {"\u015eirket \u00f6zelliklerini kar\u015f\u0131 taraf\u0131n teknik \u015fartnamesiyle madde madde kar\u015f\u0131la\u015ft\u0131r"}
          </span>
        </button>
      </div>
    </section>
  )
}

export default ModeSelector
