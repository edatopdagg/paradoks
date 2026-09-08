import type { ActiveView } from "./Sidebar"

export type WorkspaceMode =
  | "telecom"
  | "radio"
  | "compliance"
  | null

export type ThemeMode =
  | "light"
  | "dark"

type AppHeaderProps = {
  activeView: ActiveView
  workspaceMode: WorkspaceMode
  theme: ThemeMode
  sourceCount: number
  isSourcesPanelOpen: boolean

  onOpenSourcesPanel: () => void
  onChangeWorkspace: () => void
  onToggleTheme: () => void
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
      "Telekom standartlar\u0131 yapay zek\u00e2 asistan\u0131",
  },
  sources: {
    title: "Kaynaklar",
    description:
      "Sisteme aktar\u0131lan standart dok\u00fcmanlar\u0131",
  },
  history: {
    title: "Ge\u00e7mi\u015f",
    description:
      "\u00d6nceki konu\u015fmalar ve kaynak kay\u0131tlar\u0131",
  },
}

const workspaceLabels: Record<
  Exclude<WorkspaceMode, null>,
  string
> = {
  telecom: "Telekom Standartlar\u0131",
  radio: "Radyo Sistemleri",
  compliance:
    "\u015eartname Kar\u015f\u0131la\u015ft\u0131rma",
}

function AppHeader({
  activeView,
  workspaceMode,
  theme,
  sourceCount,
  isSourcesPanelOpen,
  onOpenSourcesPanel,
  onChangeWorkspace,
  onToggleTheme,
}: AppHeaderProps) {
  const currentPage =
    pageContent[activeView]

  const showWorkspaceControls =
    activeView === "chat"
    && workspaceMode !== null

  return (
    <header className="chat-header">
      <div className="header-brand">
        <h1>{currentPage.title}</h1>
        <p>{currentPage.description}</p>
      </div>

      <div className="header-controls">
        {showWorkspaceControls && (
          <>
            <div
              className={[
                "active-workspace",
                `active-workspace-${workspaceMode}`,
              ].join(" ")}
            >
              <span
                className="active-workspace-dot"
                aria-hidden="true"
              />

              <div className="active-workspace-text">
                <small>
                  {"Aktif alan"}
                </small>

                <strong>
                  {workspaceLabels[workspaceMode]}
                </strong>
              </div>
            </div>

            <div className="header-action-group">
              <button
                type="button"
                className="header-action-button"
                aria-controls="sources-panel"
                aria-expanded={
                  isSourcesPanelOpen
                }
                onClick={
                  onOpenSourcesPanel
                }
              >
                <span
                  className="header-action-icon"
                  aria-hidden="true"
                >
                  {"\u2637"}
                </span>

                <span>
                  {"Kaynaklar\u0131 G\u00f6r\u00fcnt\u00fcle"}
                </span>

                {sourceCount > 0 && (
                  <span className="source-count">
                    {sourceCount}
                  </span>
                )}
              </button>

              <button
                type="button"
                className="header-action-button change-workspace-button"
                onClick={
                  onChangeWorkspace
                }
              >
                <span
                  className="header-action-icon"
                  aria-hidden="true"
                >
                  {"\u21c4"}
                </span>

                <span>
                  {"Alan\u0131 De\u011fi\u015ftir"}
                </span>
              </button>
            </div>
          </>
        )}

        <button
          type="button"
          className="theme-toggle-button"
          onClick={onToggleTheme}
          aria-label={
            theme === "dark"
              ? "A\u00e7\u0131k temaya ge\u00e7"
              : "Koyu temaya ge\u00e7"
          }
          title={
            theme === "dark"
              ? "A\u00e7\u0131k tema"
              : "Koyu tema"
          }
        >
          <span aria-hidden="true">
            {theme === "dark"
              ? "\u2600"
              : "\u263e"}
          </span>
        </button>
      </div>
    </header>
  )
}

export default AppHeader
