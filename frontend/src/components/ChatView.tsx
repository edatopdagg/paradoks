import type { FormEvent } from "react"

import SourceCard from "./SourceCard"
import type { Source } from "../services/chatApi"

export type Message = {
  id: number
  role: "user" | "assistant"
  content: string
  sources?: Source[]
}

type ChatViewProps = {
  question: string
  messages: Message[]
  isLoading: boolean
  onQuestionChange: (question: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

const suggestions = [
  "5G ağ mimarisinin temel bileşenleri nelerdir?",
  "Bir 3GPP teknik şartnamesini özetler misin?",
  "İki farklı standart arasındaki ilişkiyi açıkla.",
]

function ChatView({
  question,
  messages,
  isLoading,
  onQuestionChange,
  onSubmit,
}: ChatViewProps) {
  return (
    <>
      {messages.length === 0 ? (
        <section className="welcome-section">
          <div className="welcome-icon">P</div>

          <h2>
            Standartlar arasında kaybolmadan sorun.
          </h2>

          <p>
            3GPP ve ilişkili telekom dokümanları
            hakkında sorularınızı kaynaklara dayalı
            olarak yanıtlayın.
          </p>

          <div className="suggestion-grid">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                disabled={isLoading}
                onClick={() =>
                  onQuestionChange(suggestion)
                }
              >
                {suggestion}
              </button>
            ))}
          </div>
        </section>
      ) : (
        <section
          className="messages-section"
          aria-label="Sohbet mesajları"
        >
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message-row ${message.role}`}
            >
              <div className="message-content">
                <div className="message-bubble">
                  {message.content}
                </div>

                {message.role === "assistant" &&
                  message.sources &&
                  message.sources.length > 0 && (
                    <div className="message-sources">
                      <h3>Kullanılan kaynaklar</h3>

                      {message.sources.map(
                        (source, index) => (
                          <SourceCard
                            key={`${source.code}-${source.clause}-${index}`}
                            source={source}
                          />
                        ),
                      )}
                    </div>
                  )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message-row assistant">
              <div className="message-content">
                <div className="message-bubble">
                  Yanıt hazırlanıyor...
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      <form
        className="prompt-area"
        onSubmit={onSubmit}
      >
        <div className="prompt-box">
          <textarea
            rows={1}
            aria-label="Mesaj"
            placeholder="Telekom standartları hakkında bir soru sorun..."
            value={question}
            disabled={isLoading}
            onChange={(event) =>
              onQuestionChange(event.target.value)
            }
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !isLoading
              ) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
          />

          <button
            type="submit"
            className="send-button"
            disabled={!question.trim() || isLoading}
          >
            {isLoading ? "Bekleyin" : "Gönder"}
          </button>
        </div>

        <p className="prompt-note">
          Yanıtlar yüklenen ve erişilebilen kaynaklara
          göre oluşturulur.
        </p>
      </form>
    </>
  )
}

export default ChatView