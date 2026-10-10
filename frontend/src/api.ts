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
import type { BudgetView, PlanningJob, PlanningJobEvent, PlanningJobRequest, ProposalPreview, ProposalRequest, ProviderDataView, ShareInvitation, TripMember, TripMessageResponse, TripVersion } from './types/v2'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
  }
}

async function requireOk(response: Response, fallback: string): Promise<Response> {
  if (!response.ok) throw new ApiError((await response.text()) || fallback, response.status)
  return response
}

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
  await requireOk(res, 'Failed to preview change')
  return res.json() as Promise<ProposalPreview>
}

export async function getV2Trip(tripId: string): Promise<TripVersion> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}`, { credentials: 'include' })
  if (!res.ok) throw new Error((await res.text()) || 'Failed to load trip')
  return res.json() as Promise<TripVersion>
}

export async function getV2Budget(tripId: string, version: number): Promise<BudgetView> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/budget?version=${version}`, { credentials: 'include' })
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
  await requireOk(res, 'Failed to apply change')
  return res.json() as Promise<TripVersion>
}

export async function sendV2TripMessage(tripId: string, message: string): Promise<TripMessageResponse> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/messages`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify({ message, idempotency_key: `message-${crypto.randomUUID()}` }) })
  await requireOk(res, 'Failed to process trip message')
  return res.json() as Promise<TripMessageResponse>
}

export async function downloadV2TripPdf(tripId: string, version: number): Promise<void> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/export.pdf?version=${version}`, { credentials: 'include' })
  await requireOk(res, 'Failed to export trip')
  const url = URL.createObjectURL(await res.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${tripId}-v${version}.pdf`
  anchor.click()
  URL.revokeObjectURL(url)
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

export async function listTripMembers(tripId: string): Promise<TripMember[]> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/members`, { credentials: 'include' })
  await requireOk(res, 'Failed to load collaborators')
  return res.json() as Promise<TripMember[]>
}

export async function removeTripMember(tripId: string, userId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/members/${encodeURIComponent(userId)}`, { method: 'DELETE', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
  await requireOk(res, 'Failed to remove collaborator')
}

export async function listTripShares(tripId: string): Promise<ShareInvitation[]> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/shares`, { credentials: 'include' })
  await requireOk(res, 'Failed to load invitations')
  return res.json() as Promise<ShareInvitation[]>
}

export async function createTripShare(tripId: string, role: 'EDITOR' | 'VIEWER'): Promise<{ invitation: ShareInvitation; token: string }> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/shares`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() }, body: JSON.stringify({ role, expires_in_hours: 24 }) })
  await requireOk(res, 'Failed to create invitation')
  return res.json() as Promise<{ invitation: ShareInvitation; token: string }>
}

export async function revokeTripShare(tripId: string, shareId: string): Promise<ShareInvitation> {
  const res = await fetch(`${API_BASE}/v2/trips/${tripId}/shares/${shareId}`, { method: 'DELETE', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
  await requireOk(res, 'Failed to revoke invitation')
  return res.json() as Promise<ShareInvitation>
}

export async function acceptTripShare(token: string): Promise<{ trip_id: string; role: string }> {
  const res = await fetch(`${API_BASE}/v2/shares/${encodeURIComponent(token)}/accept`, { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrfToken() } })
  await requireOk(res, 'Failed to accept invitation')
  return res.json() as Promise<{ trip_id: string; role: string }>
}
