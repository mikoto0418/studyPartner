import test from 'node:test'
import assert from 'node:assert/strict'
import { activeFullscreenExam, checkExamNavigation, examNavigationUnavailable, rememberExam, readExamLock } from './examNavigation.ts'

test('only ongoing fullscreen attempts lock navigation', () => {
  assert.equal(activeFullscreenExam([
    { id:'unstarted', require_fullscreen:true, attempt_status:null },
    { id:'window', require_fullscreen:false, attempt_status:'in_progress' },
    { id:'submitted', attempt_status:'submitted' },
    { id:'pending', attempt_status:'pending_review' }
  ], null), null)
  assert.equal(activeFullscreenExam([{id:'active',attempt_status:'in_progress'}],null),'active')
})
test('remembered exam is only preferred when the server still reports it ongoing', () => {
  const papers=[{id:'a',attempt_status:'in_progress'},{id:'b',attempt_status:'in_progress'}]
  assert.equal(activeFullscreenExam(papers,'b'),'b')
  assert.equal(activeFullscreenExam([{id:'b',attempt_status:'submitted'},papers[0]],'b'),'a')
  assert.equal(activeFullscreenExam([{id:'b',attempt_status:'submitted'}],'b'),null)
})

test('server restores cleared locks; failures and unrelated 403 responses cannot unlock an attempt', async () => {
  const original = { fetch: globalThis.fetch, window: globalThis.window, storage: globalThis.localStorage }
  const data = new Map([['sp_username', 'student']])
  globalThis.localStorage = {
    getItem: k => data.get(k) ?? null,
    setItem: (k, v) => data.set(k, v),
    removeItem: k => data.delete(k)
  }
  globalThis.window = { setTimeout, clearTimeout }
  const json = (status, body) => new Response(JSON.stringify(body), {status})
  try {
    globalThis.fetch = async () => json(200, {code:0, data:[{id:'active', attempt_status:'in_progress'}]})
    assert.deepEqual(await checkExamNavigation('token'), {id:'active'})
    assert.equal(readExamLock(), 'active')

    globalThis.fetch = async () => { throw new Error('offline') }
    assert.deepEqual(await checkExamNavigation('token'), {id:'active'})
    assert.equal(examNavigationUnavailable.value, false)

    globalThis.fetch = async url => url.endsWith('/auth/me')
      ? json(200, {data:{requires_identity_confirmation:false}}) : json(403, {})
    assert.deepEqual(await checkExamNavigation('token'), {id:'active'})

    globalThis.fetch = async () => json(200, {code:0, data:[{id:'active',attempt_status:'submitted'}]})
    assert.deepEqual(await checkExamNavigation('token'), {id:null})
    assert.equal(readExamLock(), null)

    globalThis.fetch = async () => { throw new Error('offline') }
    assert.deepEqual(await checkExamNavigation('token'), {id:null})
    assert.equal(examNavigationUnavailable.value, true)

    rememberExam('active')
    globalThis.fetch = async url => url.endsWith('/auth/me')
      ? json(200, {data:{requires_identity_confirmation:true}}) : json(403, {})
    assert.deepEqual(await checkExamNavigation('token'), {id:null})
    assert.equal(readExamLock(), null)
    assert.equal(examNavigationUnavailable.value, false)
  } finally {
    globalThis.fetch = original.fetch
    globalThis.window = original.window
    if (original.storage === undefined) delete globalThis.localStorage
    else globalThis.localStorage = original.storage
    examNavigationUnavailable.value = false
  }
})
