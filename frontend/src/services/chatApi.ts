export type Source = {
  org: string
  code: string
  version: string
  clause: string
  clause_title?: string
  status: string
  source_url: string
  distance: number

  source_id?: string
  document_id?: string
  version_id?: string
  clause_id?: string

  page_number?: number | null
  page_start?: number | null
  page_end?: number | null

  viewer_url?: string
  local_path?: string
  highlight_text?: string

  char_start?: number | null
  char_end?: number | null
}

export type SourceClause = {
  document_id: string
  version_id: string
  clause_id: string

  org: string
  code: string
  title?: string
  version: string
  release?: string

  clause: string
  clause_title: string
  body_text: string

  page_start?: number | null
  page_end?: number | null

  source_url: string
  local_path: string
}

export type BlockedSource = {
  org: string
  code: string
  source_url: string
}

export type PlannedQuestion = {
  text: string
  intent: string
  answered: boolean
}

export type ChatResponse = {
  conversation_id: string | null
  detected_language: "tr" | "en"
  questions: PlannedQuestion[]
  standard_answer: string
  assistant_answer: string
  reply: string
  sources: Source[]
  blocked_sources: BlockedSource[]
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000"

export async function sendChatMessage(
  message: string,
  conversationId: string,
): Promise<ChatResponse> {
  const response = await fetch(
    `${API_BASE_URL}/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
    },
  )

  if (!response.ok) {
    throw new Error(
      `Backend isteği başarısız oldu. HTTP durum kodu: ${response.status}`,
    )
  }

  return (
    await response.json()
  ) as ChatResponse
}


export async function fetchSourceClause(
  versionId: string,
  clauseId: string,
  signal?: AbortSignal,
): Promise<SourceClause> {
  const encodedVersionId = encodeURIComponent(
    versionId,
  )
  const encodedClauseId = encodeURIComponent(
    clauseId,
  )

  const response = await fetch(
    `${API_BASE_URL}/sources/${encodedVersionId}/clauses/${encodedClauseId}`,
    {
      method: "GET",
      signal,
    },
  )

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(
        "Kaynak maddesi katalogda bulunamadi.",
      )
    }

    throw new Error(
      `Kaynak maddesi alinamadi. HTTP durum kodu: ${response.status}`,
    )
  }

  return (
    await response.json()
  ) as SourceClause
}


export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/health`,
      {
        method: "GET",
      },
    )

    if (!response.ok) {
      return false
    }

    const result = (
      await response.json()
    ) as {
      status?: string
    }

    return result.status === "ok"
  } catch (error) {
    console.error(
      "Backend sağlık kontrolü başarısız oldu:",
      error,
    )

    return false
  }
}
