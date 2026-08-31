import type { TravelPlanRequest, TravelPlanResponse, PromptParseRequest, PromptParseResponse } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
