export type ActiveView =
  | "chat"
  | "sources"
  | "history"

export type ApiStatus =
  | "checking"
  | "online"
  | "offline"

type SidebarProps = {
  activeView: ActiveView
  isLoading: boolean
  apiStatus: ApiStatus
  onNewChat: () => void
  onViewChange: (view: ActiveView) => void
}

const statusContent: Record<
  ApiStatus,
  {
    label: string
    className: string
  }
> = {
  checking: {
    label: "Sistem kontrol ediliyor",
    className: "checking",
  },
  online: {
    label: "Sistem hazır",
    className: "online",
  },
  offline: {
    label: "Sistem çevrimdışı",
    className: "offline",
  },
}

function Sidebar({
  activeView,
  isLoading,
  apiStatus,
  onNewChat,
  onViewChange,
}: SidebarProps) {
  const currentStatus = statusContent[apiStatus]

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">P</div>

        <div className="brand-text">
          <strong>Paradoks</strong>
          <span>Standart Asistanı</span>
        </div>
      </div>

      <button
        type="button"
        className="new-chat-button"
        onClick={onNewChat}
        disabled={isLoading}
      >
        + Yeni sohbet
      </button>

      <nav
        className="sidebar-nav"
        aria-label="Ana menü"
      >
        <button
          type="button"
          className={`nav-item ${
            activeView === "chat" ? "active" : ""
          }`}
          onClick={() => onViewChange("chat")}
        >
          Sohbet
        </button>

        <button
          type="button"
          className={`nav-item ${
            activeView === "sources" ? "active" : ""
          }`}
          onClick={() => onViewChange("sources")}
        >
          Kaynaklar
        </button>

        <button
          type="button"
          className={`nav-item ${
            activeView === "history" ? "active" : ""
          }`}
          onClick={() => onViewChange("history")}
        >
          Geçmiş
        </button>
      </nav>

      <div
        className="sidebar-footer"
        aria-live="polite"
      >
        <span
          className={`status-dot ${currentStatus.className}`}
        />

        {currentStatus.label}
      </div>
    </aside>
  )
}

export default Sidebar