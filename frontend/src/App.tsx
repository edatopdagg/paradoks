import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react"

import AppHeader from "./components/AppHeader"
import ChatView, {
  type Message,
} from "./components/ChatView"
import HistoryView from "./components/HistoryView"
import Sidebar, {
  type ActiveView,
  type ApiStatus,
} from "./components/Sidebar"
import SourcesPanel from "./components/SourcesPanel"
import SourcesView from "./components/SourcesView"

import {
  checkApiHealth,
  sendChatMessage,
  type Source,
} from "./services/chatApi"

import {
  loadConversations,
  saveConversations,
  type SavedConversation,
} from "./services/historyStorage"

import "./App.css"

function createConversationId(): string {
  if (
    typeof crypto !== "undefined" &&
    "randomUUID" in crypto
  ) {
    return crypto.randomUUID()
  }

  return `${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`
}

function createConversationTitle(
  question: string,
): string {
  const normalizedQuestion = question
    .replace(/\s+/g, " ")
    .trim()

  if (normalizedQuestion.length <= 58) {
    return normalizedQuestion
  }

  return `${normalizedQuestion.slice(0, 58)}…`
}

function App() {
  const [question, setQuestion] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const [activeView, setActiveView] =
    useState<ActiveView>("chat")

  const [apiStatus, setApiStatus] =
    useState<ApiStatus>("checking")

  const [isSourcesPanelOpen, setIsSourcesPanelOpen] =
    useState(false)

  const [
    currentConversationId,
    setCurrentConversationId,
  ] = useState<string | null>(null)

  const [conversations, setConversations] = useState<
    SavedConversation[]
  >(() =>
    loadConversations().sort(
      (firstConversation, secondConversation) =>
        new Date(
          secondConversation.updatedAt,
        ).getTime() -
        new Date(
          firstConversation.updatedAt,
        ).getTime(),
    ),
  )

  const mainRef = useRef<HTMLElement>(null)

  const conversationSources = useMemo(() => {
    const uniqueSources = new Map<string, Source>()

    messages.forEach((message) => {
      message.sources?.forEach((source) => {
        const sourceKey = [
          source.org,
          source.code,
          source.version,
          source.clause,
          source.source_url,
        ].join("-")

        if (!uniqueSources.has(sourceKey)) {
          uniqueSources.set(sourceKey, source)
        }
      })
    })

    return Array.from(uniqueSources.values())
  }, [messages])

  useEffect(() => {
    saveConversations(conversations)
  }, [conversations])

  useEffect(() => {
    let isMounted = true

    const updateApiStatus = async () => {
      const isOnline = await checkApiHealth()

      if (isMounted) {
        setApiStatus(
          isOnline ? "online" : "offline",
        )
      }
    }

    void updateApiStatus()

    const intervalId = window.setInterval(() => {
      void updateApiStatus()
    }, 30_000)

    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  useEffect(() => {
    setIsSourcesPanelOpen(false)

    requestAnimationFrame(() => {
      window.scrollTo({
        top: 0,
        left: 0,
        behavior: "auto",
      })

      document.scrollingElement?.scrollTo({
        top: 0,
        left: 0,
        behavior: "auto",
      })

      mainRef.current?.scrollTo({
        top: 0,
        left: 0,
        behavior: "auto",
      })
    })
  }, [activeView])

  const appendMessageToConversation = (
    conversationId: string,
    message: Message,
  ) => {
    const updatedAt = new Date().toISOString()

    setConversations((currentConversations) => {
      const existingConversation =
        currentConversations.find(
          (conversation) =>
            conversation.id === conversationId,
        )

      if (!existingConversation) {
        return currentConversations
      }

      const updatedConversation: SavedConversation = {
        ...existingConversation,
        updatedAt,
        messages: [
          ...existingConversation.messages,
          message,
        ],
      }

      return [
        updatedConversation,
        ...currentConversations.filter(
          (conversation) =>
            conversation.id !== conversationId,
        ),
      ]
    })
  }

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    const trimmedQuestion = question.trim()

    if (!trimmedQuestion || isLoading) {
      return
    }

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: trimmedQuestion,
    }

    const resolvedConversationId =
      currentConversationId ??
      createConversationId()

    if (!currentConversationId) {
      const createdAt = new Date().toISOString()

      const newConversation: SavedConversation = {
        id: resolvedConversationId,
        title:
          createConversationTitle(trimmedQuestion),
        createdAt,
        updatedAt: createdAt,
        messages: [userMessage],
      }

      setCurrentConversationId(
        resolvedConversationId,
      )

      setConversations(
        (currentConversations) => [
          newConversation,
          ...currentConversations,
        ],
      )
    } else {
      appendMessageToConversation(
        resolvedConversationId,
        userMessage,
      )
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ])

    setQuestion("")
    setIsLoading(true)

    try {
      const response = await sendChatMessage(
        trimmedQuestion,
      )

      setApiStatus("online")

      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: response.reply,
        sources: response.sources,
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ])

      appendMessageToConversation(
        resolvedConversationId,
        assistantMessage,
      )
    } catch (error) {
      console.error(
        "Sohbet isteği başarısız oldu:",
        error,
      )

      setApiStatus("offline")

      const errorMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content:
          "Backend servisine ulaşılamadı. Lütfen FastAPI sunucusunun çalıştığını kontrol edin.",
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        errorMessage,
      ])

      appendMessageToConversation(
        resolvedConversationId,
        errorMessage,
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    if (isLoading) {
      return
    }

    setCurrentConversationId(null)
    setMessages([])
    setQuestion("")
    setActiveView("chat")
    setIsSourcesPanelOpen(false)
  }

  const handleOpenConversation = (
    conversation: SavedConversation,
  ) => {
    setCurrentConversationId(conversation.id)
    setMessages(conversation.messages)
    setQuestion("")
    setIsSourcesPanelOpen(false)
    setActiveView("chat")
  }

  const handleDeleteConversation = (
    conversationId: string,
  ) => {
    setConversations(
      (currentConversations) =>
        currentConversations.filter(
          (conversation) =>
            conversation.id !== conversationId,
        ),
    )

    if (
      currentConversationId === conversationId
    ) {
      setCurrentConversationId(null)
      setMessages([])
      setQuestion("")
      setIsSourcesPanelOpen(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeView={activeView}
        isLoading={isLoading}
        apiStatus={apiStatus}
        onNewChat={handleNewChat}
        onViewChange={setActiveView}
      />

      <main
        ref={mainRef}
        className="chat-page"
      >
        <AppHeader
          activeView={activeView}
          isSourcesPanelOpen={isSourcesPanelOpen}
          onOpenSourcesPanel={() =>
            setIsSourcesPanelOpen(true)
          }
        />

        {activeView === "chat" && (
          <ChatView
            question={question}
            messages={messages}
            isLoading={isLoading}
            onQuestionChange={setQuestion}
            onSubmit={handleSubmit}
          />
        )}

        {activeView === "sources" && (
          <SourcesView
            sources={conversationSources}
          />
        )}

        {activeView === "history" && (
          <HistoryView
            conversations={conversations}
            onOpenConversation={
              handleOpenConversation
            }
            onDeleteConversation={
              handleDeleteConversation
            }
          />
        )}
      </main>

      {isSourcesPanelOpen && (
        <SourcesPanel
          sources={conversationSources}
          onClose={() =>
            setIsSourcesPanelOpen(false)
          }
        />
      )}
    </div>
  )
}

export default App