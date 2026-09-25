import assert from 'node:assert/strict'
import test from 'node:test'

const module = await import('./answerEditDiff.ts').catch(() => ({}))
const diffAnswerText = module.diffAnswerText

test('captures inserted text and exact position', () => {
  assert.equal(typeof diffAnswerText, 'function', 'answer edit diff helper must exist')
  assert.deepEqual(diffAnswerText('已有答案：', '已有答案：新增内容'), {
    operation: 'insert', position: 5, insertedText: '新增内容', deletedText: ''
  })
})

test('captures the exact text deleted from the middle', () => {
  assert.equal(typeof diffAnswerText, 'function', 'answer edit diff helper must exist')
  assert.deepEqual(diffAnswerText('甲需要删除这段内容乙', '甲乙'), {
    operation: 'delete', position: 1, insertedText: '', deletedText: '需要删除这段内容'
  })
})

test('captures replacement text without losing either side', () => {
  assert.equal(typeof diffAnswerText, 'function', 'answer edit diff helper must exist')
  assert.deepEqual(diffAnswerText('答案甲乙。', '答案丙丁。'), {
    operation: 'replace', position: 2, insertedText: '丙丁', deletedText: '甲乙'
  })
})

test('reports unchanged text as no operation', () => {
  assert.equal(typeof diffAnswerText, 'function', 'answer edit diff helper must exist')
  assert.deepEqual(diffAnswerText('原样保留', '原样保留'), {
    operation: 'none', position: 4, insertedText: '', deletedText: ''
  })
})
