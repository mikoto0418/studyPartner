import { ref } from 'vue'

export const examNavigationUnavailable = ref(false)
const key = () => `sp_exam_lock:${localStorage.getItem('sp_username') || ''}`
export function readExamLock(): string | null {
  try { return localStorage.getItem(key()) } catch { return null }
}
export function rememberExam(id: string) {
  try { localStorage.setItem(key(), id) } catch { /* Server lookup remains authoritative. */ }
}
export function forgetExam(id?: string) {
  try { if (!id || readExamLock() === id) localStorage.removeItem(key()) } catch { /* no-op */ }
}

export interface ExamSession {
  id: string
  require_fullscreen?: boolean
  attempt_status?: string | null
}
export function activeFullscreenExam(papers: ExamSession[], preferred: string | null): string | null {
  const active = papers.filter(p => p.require_fullscreen !== false && p.attempt_status === 'in_progress')
  return active.find(p => p.id === preferred)?.id ?? active[0]?.id ?? null
}

// Use a read-only request, without the shared request interceptor's router redirects.
export async function checkExamNavigation(token: string): Promise<{ id: string | null; unauthorized?: boolean }> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 5000)
  try {
    const base = import.meta.env?.VITE_API_BASE_URL || '/api/v1'
    const response = await fetch(`${base}/assessment/student/papers`, {
      headers: { Authorization: `Bearer ${token}` }, signal: controller.signal, cache: 'no-store'
    })
    if (response.status === 401) return { id: null, unauthorized: true }
    // Only the explicit identity gate can bypass this check. Other permission
    // failures do not prove that the student has no ongoing attempt.
    if (response.status === 403) {
      const me = await fetch(`${base}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }, signal: controller.signal, cache: 'no-store'
      })
      if (me.ok && (await me.json()).data?.requires_identity_confirmation === true) {
        forgetExam(); examNavigationUnavailable.value = false
        return { id: null }
      }
      throw new Error('Cannot confirm permission to access exam status')
    }
    if (!response.ok) throw new Error('Cannot confirm exam status')
    const body = await response.json()
    if (body.code !== 0 || !Array.isArray(body.data)) throw new Error('Invalid exam status')
    const id = activeFullscreenExam(body.data, readExamLock())
    if (id) rememberExam(id)
    else forgetExam()
    examNavigationUnavailable.value = false
    return { id }
  } catch {
    const id = readExamLock()
    // A failed request must not unlock a potentially ongoing exam.
    examNavigationUnavailable.value = !id
    return { id }
  } finally { window.clearTimeout(timeout) }
}
