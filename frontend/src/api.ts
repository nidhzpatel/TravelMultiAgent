import type {
  TravelPlanRequest,
  TravelPlanResponse,
  PromptParseRequest,
  PromptParseResponse,
  ChatCreateRequest,
  ChatMessageRequest,
  ChatMessageResponse,
  ChatSession,
} from './types'
import type { BudgetView, PlanningJob, PlanningJobEvent, PlanningJobRequest, ProposalPreview, ProposalRequest, ProviderDataView, TripVersion } from './types/v2'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function csrfToken(): string {
  return document.cookie.match(/(?:^|; )vm_csrf=([^;]*)/)?.[1] ?? ''
}

export async function startPlan(
  request: TravelPlanRequest,
  signal?: AbortSignal,
): Promise<TravelPlanResponse> {
  const res = await fetch(`${API_BASE}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Failed to generate plan')
  }

  return res.json() as Promise<TravelPlanResponse>
}

export async function parsePrompt(
  request: PromptParseRequest,
  signal?: AbortSignal,
): Promise<PromptParseResponse> {
  const res = await fetch(`${API_BASE}/parse-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Failed to parse prompt')
  }

  return res.json() as Promise<PromptParseResponse>
}

export async function healthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`)
  return res.json() as Promise<{ status: string }>
}

export async function createChat(
  request: ChatCreateRequest,
  signal?: AbortSignal,
): Promise<ChatMessageResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Failed to create chat')
  }

  return res.json() as Promise<ChatMessageResponse>
}

export async function sendChatMessage(
  sessionId: string,
  request: ChatMessageRequest,
  signal?: AbortSignal,
): Promise<ChatMessageResponse> {
  const res = await fetch(`${API_BASE}/chat/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Failed to send message')
  }

  return res.json() as Promise<ChatMessageResponse>
}

export async function getChat(sessionId: string): Promise<ChatSession> {
  const res = await fetch(`${API_BASE}/chat/${sessionId}`)

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Failed to load chat')
  }

  return res.json() as Promise<ChatSession>
}

export async function listChats(): Promise<ChatSession[]> {
  const res = await fetch(`${API_BASE}/chats`)

  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Failed to list chats')
  }

  return res.json() as Promise<ChatSession[]>
}

export async function previewTripProposal(tripId: string, request: ProposalRequest): Promise<ProposalPreview> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/proposals`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify(request) })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to preview change')
  return res.json() as Promise<ProposalPreview>
}

export async function getV2Trip(tripId: string): Promise<TripVersion> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load trip')
  return res.json() as Promise<TripVersion>
}

export async function getV2Budget(tripId: string): Promise<BudgetView> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/budget`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load budget')
  return res.json() as Promise<BudgetView>
}

export async function getV2ProviderData(tripId: string, version: number): Promise<ProviderDataView> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/provider-data?version=${version}`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load provider data')
  return res.json() as Promise<ProviderDataView>
}

export async function commitTripProposal(tripId: string, proposalId: string): Promise<TripVersion> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/proposals/${proposalId}/commit`, { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to apply change')
  return res.json() as Promise<TripVersion>
}

export async function createPlanningJob(tripId: string, request: PlanningJobRequest): Promise<PlanningJob> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/planning-jobs`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify(request) })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to start planning')
  return res.json() as Promise<PlanningJob>
}

export async function listPlanningJobs(tripId: string): Promise<PlanningJob[]> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/planning-jobs`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load planning jobs')
  return res.json() as Promise<PlanningJob[]>
}

export async function getPlanningJob(tripId: string, jobId: string): Promise<PlanningJob> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/planning-jobs/${jobId}`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load planning status')
  return res.json() as Promise<PlanningJob>
}

export async function getPlanningJobEvents(tripId: string, jobId: string, after = 0): Promise<PlanningJobEvent[]> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/planning-jobs/${jobId}/events?after=${after}`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load planning progress')
  return res.json() as Promise<PlanningJobEvent[]>
}

export async function cancelPlanningJob(tripId: string, jobId: string): Promise<PlanningJob> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/planning-jobs/${jobId}/cancel`, { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to cancel planning')
  return res.json() as Promise<PlanningJob>
}
