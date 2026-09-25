export type AnswerEditOperation = 'insert' | 'delete' | 'replace' | 'none'

export interface AnswerEditDiff {
  operation: AnswerEditOperation
  /** UTF-16 offset matching textarea selectionStart/selectionEnd offsets. */
  position: number
  insertedText: string
  deletedText: string
}

/** Return the smallest contiguous diff that transforms previous into current. */
export function diffAnswerText(previous: string, current: string): AnswerEditDiff {
  let prefix = 0
  const prefixLimit = Math.min(previous.length, current.length)
  while (prefix < prefixLimit && previous[prefix] === current[prefix]) prefix += 1

  let suffix = 0
  const suffixLimit = Math.min(previous.length - prefix, current.length - prefix)
  while (
    suffix < suffixLimit &&
    previous[previous.length - suffix - 1] === current[current.length - suffix - 1]
  ) {
    suffix += 1
  }

  const deletedText = previous.slice(prefix, previous.length - suffix)
  const insertedText = current.slice(prefix, current.length - suffix)
  const operation: AnswerEditOperation = deletedText
    ? insertedText ? 'replace' : 'delete'
    : insertedText ? 'insert' : 'none'

  return { operation, position: prefix, insertedText, deletedText }
}
