import test from 'node:test'
import assert from 'node:assert/strict'
import { codeEditorEdit } from './codeEditor.ts'

function run(value, start, end, key, shift = false, language = 'python') {
  const e = codeEditorEdit(value, start, end, key, shift, language)
  return e && { value: value.slice(0, e.from) + e.text + value.slice(e.to), start: e.start, end: e.end }
}

test('Tab reaches the next four-space stop and works before the first newline', () => {
  assert.deepEqual(run('ab', 2, 2, 'Tab'), { value: 'ab  ', start: 4, end: 4 })
  assert.deepEqual(run('\n', 0, 0, 'Tab'), { value: '    \n', start: 4, end: 4 })
})
test('selected lines indent and outdent; selection ending at next line start excludes that line', () => {
  assert.deepEqual(run('abc', 0, 3, 'Tab'), { value: '    abc', start: 4, end: 7 })
  const value = 'a\nb\nc'
  assert.deepEqual(run(value, 0, 4, 'Tab'), { value: '    a\n    b\nc', start: 4, end: 12 })
  assert.deepEqual(run('    a\n    b\nc', 4, 12, 'Tab', true), { value, start: 0, end: 4 })
})
test('Shift+Tab removes one tab or up to four spaces without deleting code', () => {
  assert.deepEqual(run('\tx', 2, 2, 'Tab', true), { value: 'x', start: 1, end: 1 })
  assert.deepEqual(run('  x', 1, 1, 'Tab', true), { value: 'x', start: 0, end: 0 })
  assert.equal(run('x', 1, 1, 'Tab', true).value, 'x')
})
test('brackets and quotes pair with the cursor inside; selections are wrapped', () => {
  for (const [open, close] of [['(',')'],['[',']'],['{','}'],['"','"'],["'","'"]]) {
    assert.deepEqual(run('', 0, 0, open), { value: open + close, start: 1, end: 1 })
    assert.deepEqual(run('abc', 0, 3, open), { value: open + 'abc' + close, start: 1, end: 4 })
  }
})
test('typing an existing closing bracket or quote moves past it; backspace removes an empty pair', () => {
  assert.deepEqual(run('()', 1, 1, ')'), { value: '()', start: 2, end: 2 })
  assert.deepEqual(run('""', 1, 1, '"'), { value: '""', start: 2, end: 2 })
  assert.deepEqual(run('[]', 1, 1, 'Backspace'), { value: '', start: 0, end: 0 })
})
test('Enter preserves indentation, indents Python blocks, and splits paired braces', () => {
  assert.deepEqual(run('    x', 5, 5, 'Enter'), { value: '    x\n    ', start: 10, end: 10 })
  assert.deepEqual(run('if True: # comment', 18, 18, 'Enter'), { value: 'if True: # comment\n    ', start: 23, end: 23 })
  assert.deepEqual(run('  {}', 3, 3, 'Enter', false, 'cpp'), { value: '  {\n      \n  }', start: 10, end: 10 })
})
test('strings, escaped quotes and comments do not receive unwanted pairs', () => {
  assert.equal(run('"text', 5, 5, '('), null)
  assert.equal(run('# comment', 9, 9, '('), null)
  assert.equal(run('// comment', 10, 10, '{', false, 'cpp'), null)
  assert.equal(run('/* comment', 10, 10, '(', false, 'c'), null)
  assert.equal(run('"a\\"', 3, 3, '"'), null)
  assert.equal(run('abc', 1, 1, '('), null)
})
