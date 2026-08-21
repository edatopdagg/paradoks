import type { ActiveView } from "./Sidebar"

type AppHeaderProps = {
  activeView: ActiveView
  isSourcesPanelOpen: boolean
  onOpenSourcesPanel: () => void
}

const pageContent: Record<
  ActiveView,
  {
    title: string
    description: string
  }
> = {
  chat: {
    title: "Paradoks",
    description:
      "Telekom standartları yapay zekâ asistanı",
  },
  sources: {
    title: "Kaynaklar",
    description:
      "Sisteme aktarılan standart dokümanları",
  },
  history: {
    title: "Geçmiş",
    description:
      "Önceki konuşmalar ve kaynak kayıtları",
  },
}

function AppHeader({
  activeView,
  isSourcesPanelOpen,
  onOpenSourcesPanel,
}: AppHeaderProps) {
  const currentPage = pageContent[activeView]

  return (
    <header className="chat-header">
      <div>
        <h1>{currentPage.title}</h1>
        <p>{currentPage.description}</p>
      </div>

      {activeView === "chat" && (
        <button
          type="button"
          className="source-button"
          aria-controls="sources-panel"
          aria-expanded={isSourcesPanelOpen}
          onClick={onOpenSourcesPanel}
        >
          Kaynakları görüntüle
        </button>
      )}
    </header>
  )
}

export default AppHeader