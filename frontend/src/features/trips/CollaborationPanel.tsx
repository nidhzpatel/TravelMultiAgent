import { Copy, UserMinus, UserPlus, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiError, createTripShare, listTripMembers, listTripShares, removeTripMember, revokeTripShare } from '../../api'
import type { ShareInvitation, TripMember } from '../../types/v2'

interface CollaborationPanelProps { tripId: string }

export default function CollaborationPanel({ tripId }: CollaborationPanelProps) {
  const [members, setMembers] = useState<TripMember[]>([])
  const [shares, setShares] = useState<ShareInvitation[]>([])
  const [role, setRole] = useState<'EDITOR' | 'VIEWER'>('VIEWER')
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [available, setAvailable] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    try {
      const [nextMembers, nextShares] = await Promise.all([listTripMembers(tripId), listTripShares(tripId)])
      setMembers(nextMembers); setShares(nextShares); setAvailable(true)
    } catch (reason) {
      if (reason instanceof ApiError && (reason.status === 403 || reason.status === 404)) setAvailable(false)
      else setError(reason instanceof Error ? reason.message : 'Unable to load collaboration')
    }
  }
  useEffect(() => { void reload() }, [tripId])
  if (!available) return null

  async function create() {
    setError(null)
    try {
      const created = await createTripShare(tripId, role)
      const url = new URL(window.location.href)
      url.search = ''
      url.searchParams.set('share_token', created.token)
      setShareUrl(url.toString())
      await reload()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to create invitation') }
  }

  async function removeMember(userId: string) {
    setError(null)
    try { await removeTripMember(tripId, userId); await reload() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to remove member') }
  }

  async function revoke(shareId: string) {
    setError(null)
    try { await revokeTripShare(tripId, shareId); await reload() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to revoke invitation') }
  }

  async function copyShareUrl() {
    if (!shareUrl) return
    try { await navigator.clipboard.writeText(shareUrl) }
    catch { setError('Copy failed. Select and copy the invitation link manually.') }
  }

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-950/70 p-4" aria-label="Trip collaboration">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-300">Collaboration</p>
      <div className="mt-3 flex gap-2"><select aria-label="Invitation role" value={role} onChange={(event) => setRole(event.target.value as 'EDITOR' | 'VIEWER')} className="min-w-0 flex-1 rounded-lg border border-white/15 bg-slate-900 px-2 py-2 text-sm text-white"><option value="VIEWER">Viewer</option><option value="EDITOR">Editor</option></select><button type="button" onClick={() => void create()} className="rounded-lg border border-violet-300/30 p-2 text-violet-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-200" aria-label="Create invitation"><UserPlus className="h-4 w-4" /></button></div>
      {shareUrl && <div className="mt-3 rounded-lg bg-violet-400/10 p-3"><p className="break-all text-xs text-violet-100">{shareUrl}</p><button type="button" onClick={() => void copyShareUrl()} className="mt-2 inline-flex items-center gap-1 text-xs text-violet-200"><Copy className="h-3.5 w-3.5" />Copy one-time link</button></div>}
      <ul className="mt-3 space-y-2">{members.map((member) => <li key={member.user_id} className="flex items-center justify-between gap-2 text-sm"><span className="min-w-0 truncate text-slate-200">{member.user_id} <span className="text-xs text-slate-500">{member.role}</span></span>{member.role !== 'OWNER' && <button type="button" aria-label={`Remove ${member.user_id}`} onClick={() => void removeMember(member.user_id)} className="text-rose-300"><UserMinus className="h-4 w-4" /></button>}</li>)}</ul>
      {shares.some((item) => item.revoked_at === null && item.accepted_at === null) && <div className="mt-4 border-t border-white/10 pt-3"><p className="text-xs text-slate-500">Active invitations</p>{shares.filter((item) => item.revoked_at === null && item.accepted_at === null).map((item) => <div key={item.id} className="mt-2 flex items-center justify-between text-xs text-slate-300"><span>{item.role} · expires {new Date(item.expires_at).toLocaleString()}</span><button type="button" aria-label="Revoke invitation" onClick={() => void revoke(item.id)} className="text-rose-300"><X className="h-4 w-4" /></button></div>)}</div>}
      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
    </section>
  )
}
