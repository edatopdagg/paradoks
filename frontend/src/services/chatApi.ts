export type ChatDomain = "telecom" | "radio"

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
  domain: ChatDomain = "telecom",
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
        domain,
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


export type ComplianceEvidence = {
  company_row: number
  source_filename: string
  source_page: number | null
  source_kind: string
  text: string
  score: number
  values: Record<string, string>
}

export type ComplianceResult = {
  requirement_index: number
  specification_row: number
  specification_source_filename: string
  specification_source_page: number | null
  specification_source_kind: string
  requirement: string
  requirement_values: Record<string, string>
  status: "FC" | "PC" | "NC" | "REVIEW"
  best_score: number
  evidence: ComplianceEvidence | null
  candidates: ComplianceEvidence[]
  explanation: string
}

export type ExtraCapability = {
  company_row: number
  source_filename: string
  source_page: number | null
  source_kind: string
  capability: string
  values: Record<string, string>
}

export type ComplianceResponse = {
  summary: {
    total_requirements: number
    fully_compliant: number
    partially_compliant: number
    non_compliant: number
    manual_review: number
    coverage_percent: number
  }
  results: ComplianceResult[]
  extra_capabilities: ExtraCapability[]
  company_row_count: number
  specification_row_count: number
}

export async function compareCompliance(
  companyFiles: File[],
  specificationFiles: File[],
): Promise<ComplianceResponse> {
  if (companyFiles.length === 0) {
    throw new Error(
      "En az bir \u015firket \u00f6zellik dosyas\u0131 se\u00e7melisiniz.",
    )
  }

  if (specificationFiles.length === 0) {
    throw new Error(
      "En az bir \u015fartname dosyas\u0131 se\u00e7melisiniz.",
    )
  }

  const body = new FormData()

  for (const file of companyFiles) {
    body.append(
      "company_files",
      file,
    )
  }

  for (const file of specificationFiles) {
    body.append(
      "specification_files",
      file,
    )
  }

  const response = await fetch(
    `${API_BASE_URL}/compliance/compare`,
    {
      method: "POST",
      body,
    },
  )

  if (!response.ok) {
    let detail =
      `HTTP ${response.status}`

    try {
      const payload =
        await response.json()

      if (payload?.detail) {
        detail = String(
          payload.detail,
        )
      }
    } catch {
      // response body is not JSON
    }

    throw new Error(
      `Kar\u015f\u0131la\u015ft\u0131rma ba\u015far\u0131s\u0131z: ${detail}`,
    )
  }

  return (
    await response.json()
  ) as ComplianceResponse
}
