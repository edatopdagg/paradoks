import type { Message } from "../components/ChatView"

export type SavedConversation = {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: Message[]
}

const STORAGE_KEY = "paradoks-chat-history"

export function loadConversations(): SavedConversation[] {
  try {
    const storedValue = localStorage.getItem(STORAGE_KEY)

    if (!storedValue) {
      return []
    }

    const parsedValue = JSON.parse(
      storedValue,
    ) as SavedConversation[]

    return Array.isArray(parsedValue)
      ? parsedValue
      : []
  } catch (error) {
    console.error(
      "Sohbet geçmişi okunamadı:",
      error,
    )

    return []
  }
}

export function saveConversations(
  conversations: SavedConversation[],
): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(conversations),
    )
  } catch (error) {
    console.error(
      "Sohbet geçmişi kaydedilemedi:",
      error,
    )
  }
}