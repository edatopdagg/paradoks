import type { SavedConversation } from "../services/historyStorage"

type HistoryViewProps = {
  conversations: SavedConversation[]
  onOpenConversation: (
    conversation: SavedConversation,
  ) => void
  onDeleteConversation: (
    conversationId: string,
  ) => void
}

function formatConversationDate(
  dateValue: string,
): string {
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(dateValue))
}

function HistoryView({
  conversations,
  onOpenConversation,
  onDeleteConversation,
}: HistoryViewProps) {
  return (
    <section className="workspace-view">
      <div className="workspace-view-header">
        <div>
          <span className="workspace-eyebrow">
            Konuşma kayıtları
          </span>

          <h2>Geçmiş</h2>

          <p>
            Önceki konuşmalarınızı tekrar açabilir
            veya artık ihtiyacınız olmayan kayıtları
            silebilirsiniz.
          </p>
        </div>
      </div>

      {conversations.length === 0 ? (
        <div className="workspace-empty-state">
          <div className="workspace-empty-icon">P</div>

          <h3>Henüz kayıtlı sohbet yok</h3>

          <p>
            İlk sorunuzu gönderdiğinizde konuşma
            otomatik olarak tarayıcınıza
            kaydedilecek.
          </p>
        </div>
      ) : (
        <div className="history-list">
          {conversations.map((conversation) => (
            <article
              key={conversation.id}
              className="history-card"
            >
              <button
                type="button"
                className="history-card-main"
                onClick={() =>
                  onOpenConversation(conversation)
                }
              >
                <strong>{conversation.title}</strong>

                <span>
                  {formatConversationDate(
                    conversation.updatedAt,
                  )}
                </span>

                <small>
                  {conversation.messages.length} mesaj
                </small>
              </button>

              <button
                type="button"
                className="history-delete-button"
                aria-label={`${conversation.title} sohbetini sil`}
                onClick={() =>
                  onDeleteConversation(
                    conversation.id,
                  )
                }
              >
                Sil
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export default HistoryView