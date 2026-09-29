import request from '../request'

export interface AssessmentPaper {
  id: string
  title: string
  description?: string | null
  source_file_id?: string | null
  parse_status: string
  parse_progress?: Record<string, any> | null
  parse_error?: string | null
  question_count: number
  /** 有题目未设置分值时整卷满分为未知，后端返回 null */
  total_score?: number | null
  publish_target?: Record<string, any> | null
  publish_at?: string | null
  published_at?: string | null
  /** 主观题批阅倾向：{mode: lenient/standard/strict, extra} */
  grading_preference?: { mode: string; extra?: string } | null
  created_at: string
  updated_at: string
}

export interface AssessmentQuestion {
  id: string
  paper_id: string
  order_index: number
  question_type: string
  stem: string
  stem_images?: any[] | null
  options?: any[] | null
  answer?: any
  analysis?: string | null
  /** null = 原文没标分值、教师尚未填写 */
  score?: number | null
  difficulty?: number | null
  tags?: string[] | null
  source_chunk?: any
  created_at: string
  updated_at: string
}

export interface ParseStatus {
  parse_status: string
  parse_progress?: Record<string, any> | null
  parse_error?: string | null
  question_count: number
  total_score?: number | null
}

export interface StudentPaper {
  id: string
  title: string
  description?: string | null
  question_count: number
  total_score?: number | null
  published_at?: string | null
  due_at?: string | null
  time_limit_minutes?: number | null
  /** 未配置的老数据按 true 处理 */
  require_fullscreen?: boolean
  attempt_id?: string | null
  attempt_status?: string | null
  attempt_score?: number | null
}

export interface CodeRunCase {
  index: number
  /** null = 自测没有期望输出可比，只说明跑成没跑成 */
  passed?: boolean | null
  status: string
  input: string
  actual_output: string
  stderr: string
  time_ms?: number | null
}

export interface CodeRunResult {
  status: string
  message: string
  compile_output: string
  cases: CodeRunCase[]
  runs_left: number
}

export interface StudentReview {
  paper: { id: string; title: string; total_score: number | null }
  attempt: {
    status: string
    score: number | null
    objective_score: number
    duration_seconds: number | null
  }
  questions: Array<{
    question_id: string
    order_index: number
    question_type: string
    stem: string
    stem_images?: any[] | null
    options?: Array<{ key?: string; text?: string }> | null
    max_score: number | null
    student_answer: any
    score: number | null
    graded: boolean
    is_correct: boolean | null
    reference_answer: any
    analysis?: string | null
    language?: string | null
    /** 只含通过数，不含用例内容 */
    judge_summary?: { status: string; passed: number; total: number } | null
  }>
}

export interface AnalyticsOverview {
  assigned: number
  finished: number
  in_progress: number
  pending_review: number
  avg_score: number | null
  max_score: number | null
  min_score: number | null
  total_score: number | null
  pass_rate: number | null
  avg_duration_seconds: number | null
}

export interface ScoreBucket {
  label: string
  range: string
  count: number
}

export interface QuestionStat {
  question_id: string
  order_index: number
  question_type: string
  answered: number
  /** 已批改份数。主观题只按已批改的算得分率，与 answered 不等时要让教师看见 */
  graded: number
  correct: number | null
  accuracy: number | null
  avg_score_rate: number | null
  avg_dwell_seconds?: number | null
}

export interface BehaviorStat {
  event_type: string
  count: number
  is_flag: boolean
}

export interface PaperAnalytics {
  paper: {
    id: string
    title: string
    question_count: number
    total_score: number | null
  }
  overview: AnalyticsOverview
  score_distribution: ScoreBucket[]
  questions: QuestionStat[]
  behavior_distribution: BehaviorStat[]
  suspicious_count: number
}

export interface AttemptInsights {
  attempt: {
    id: string
    student_id: string
    status: string
    score: number | null
    duration_seconds: number | null
    flag_count: number
  }
  questions: Array<{
    question_id: string
    order_index: number
    question_type: string
    dwell_seconds: number
    dwell_events: number
    paste_events: number
    paste_chars: number
    edit_count: number
    inserted_chars: number
    typed_chars: number
    ime_chars: number
    non_key_input_chars: number
    deleted_chars: number
    flag_count: number
    class_avg_dwell_seconds: number | null
  }>
}

export interface ClassExamAnalytics {
  class_info: { id: string; name: string; student_count: number }
  summary: {
    paper_count: number
    assigned_total: number
    finished_total: number
    avg_score_rate: number | null
    pass_rate: number | null
    suspicious_attempts: number
    pending_review_total: number
  }
  papers: Array<{
    paper_id: string
    title: string
    published_at: string | null
    total_score: number | null
    assigned: number
    finished: number
    avg_score_rate: number | null
    pass_rate: number | null
    avg_duration_seconds: number | null
  }>
  students: Array<{
    student_id: string
    name: string
    attempted: number
    avg_score_rate: number | null
    flag_count: number
    pending_review: number
  }>
}

export interface CodeTestCase {
  input: string
  expected_output: string
}

export interface StudentQuestion {
  id: string
  order_index: number
  question_type: string
  stem: string
  stem_images?: any[] | null
  options?: any[] | null
  /** null = 该题尚未设置分值 */
  score?: number | null
  /** 编程题：python / javascript / java */
  language?: string | null
  starter_code?: string | null
}

export interface StudentAttempt {
  id: string
  paper_id: string
  status: string
  started_at?: string | null
  submitted_at?: string | null
  score?: number | null
  duration_seconds?: number | null
  /** 整卷截止与开考限时中较早的那个 */
  answer_deadline?: string | null
  /** 交卷时超过截止宽限期，本次提交的答案未落库 */
  answers_ignored?: boolean
}

export interface StudentAnswerIn {
  question_id: string
  answer?: any
}

export interface StudentAnswerOut {
  question_id: string
  answer?: any
}

export interface StudentAnswersOut {
  attempt_id?: string | null
  status?: string | null
  answers: StudentAnswerOut[]
}

export interface BehaviorEventPayload {
  event_type: string
  payload?: Record<string, any>
  occurred_at?: string
}

export interface AttemptAnswer {
  question_id: string
  order_index: number
  question_type: string
  stem: string
  options?: any[] | null
  reference_answer?: any
  /** null = 题目未设置分值，批改页应禁用打分输入 */
  max_score?: number | null
  answer?: any
  score: number
  graded: boolean
  is_correct?: boolean | null
  /** 编程题判题结果：只有通过数，不含隐藏用例内容 */
  language?: string | null
  judge_summary?: { status: string; passed: number; total: number } | null
  /** 教师端可见的逐用例明细（含隐藏用例） */
  judge_detail?: {
    status: string
    passed: number
    total: number
    message?: string
    compile_output?: string
    cases?: Array<{
      index: number
      passed: boolean
      status: string
      input: string
      expected: string
      actual: string
      stderr: string
      time_ms?: number | null
    }>
  } | null
  /** AI 预批阅建议，教师确认前只是参考值 */
  ai_suggested_score?: number | null
  ai_comment?: string | null
  ai_graded_at?: string | null
}

export interface AIGradeItem {
  question_id: string
  suggested_score?: number | null
  max_score?: number | null
  comment: string
  error?: string | null
}

export interface AIGradeResult {
  graded: number
  failed: number
  skipped: number
  items: AIGradeItem[]
}

export interface AttemptMonitor {
  id: string
  student_id: string
  student_name: string
  username: string
  status: string
  started_at?: string | null
  submitted_at?: string | null
  duration_seconds?: number | null
  score?: number | null
  suspicious: boolean
  event_count: number
  flagged_count: number
  pending_grade_count: number
}

export interface BehaviorEventOut {
  id: string
  event_type: string
  payload?: Record<string, any> | null
  occurred_at?: string | null
}

/**
 * 导入试卷用的「标准包」模板：paper.json 的内容示例。
 *
 * 包结构（zip）：
 *   你的包.zip
 *   ├── paper.json   ← 下面这段就是它的示例
 *   └── assets/      ← 题目图片，文件名建议 image-1.jpg、image-2.jpg …
 *
 * 图片编号规则：题干里的 [[IMG:n]] 是「全卷统一编号」，不是每题从 1 开始；
 * 题目 images 里的 index 必须和它一致（详见 IMPORT_PACKAGE_GUIDE）。
 *
 * 注意：走「上传 Word/PDF → AI 拆题」时平台会自动抽图挂好，老师不用手写 images。
 */
export const IMPORT_TEMPLATE_JSON = `{
  "paper": {
    "title": "示例卷名（必填）",
    "description": "可选：考试说明、分值分布、提交方式等，可整段写在这里"
  },
  "questions": [
    {
      "order_index": 0,
      "question_type": "code",
      "stem": "开启编程之旅：打印输出 hello world。图示：[[IMG:1]]",
      "images": [{ "asset": "assets/image-1.jpg", "index": 1 }],
      "language": "c",
      "starter_code": "",
      "test_cases": [],
      "answer": "",
      "analysis": "",
      "score": 5
    },
    {
      "order_index": 1,
      "question_type": "single",
      "stem": "下面哪个是变量声明？图示：[[IMG:2]]",
      "images": [{ "asset": "assets/image-2.jpg", "index": 2 }],
      "options": [
        { "key": "A", "text": "int a;" },
        { "key": "B", "text": "a = 1" }
      ],
      "answer": "A",
      "analysis": "只有 A 是声明。",
      "score": 5
    },
    {
      "order_index": 2,
      "question_type": "code",
      "stem": "进阶：给出下图（图 1-图 5）中各段代码的时间复杂度。图 1：[[IMG:3]]；图 2：[[IMG:4]]；图 3：[[IMG:5]]；图 4：[[IMG:6]]；图 5：[[IMG:7]]",
      "images": [
        { "asset": "assets/image-3.jpg", "index": 3 },
        { "asset": "assets/image-4.jpg", "index": 4 },
        { "asset": "assets/image-5.jpg", "index": 5 },
        { "asset": "assets/image-6.jpg", "index": 6 },
        { "asset": "assets/image-7.jpg", "index": 7 }
      ],
      "language": "c",
      "starter_code": "",
      "test_cases": [],
      "answer": "",
      "analysis": "",
      "score": 10
    }
  ]
}`

/** 「导入包」说明文案。同时写进 zip 的 使用说明.txt，并在问号抽屉里展示。 */
export const IMPORT_PACKAGE_GUIDE = `【导入包说明】

一、包长什么样（zip）
  你的包.zip
  ├── paper.json        ← 题目内容（本模板就是它的示例）
  └── assets/           ← 题目图片，文件名建议 image-1.jpg、image-2.jpg …
       ├── image-1.jpg
       └── image-2.jpg

二、图片怎么对应到题干
  1. 题干里要插图的位置写占位符 [[IMG:n]]。n 是「全卷统一编号」，不是每题从 1 开始：
     第 1 题用 image-1.jpg，第 3 题接着用 image-3.jpg。
  2. 在题目的 images 里写 { "asset": "assets/image-N.jpg", "index": N }，
     其中 index 必须和 [[IMG:n]] 的 n 一致。
  3. 一道题要多张图，就在 images 里按顺序写多条（见模板第 3 题，一题 5 张图）。

三、两种导入方式（发题工作台 →「导入 JSON/压缩包」）
  · 纯 JSON：图片改写成外链，images 写成 { "url": "https://…", "index": n }。
  · zip 包：图片放 assets/，JSON 里用相对路径 assets/…（推荐，不依赖外网）。

四、老师不用自己抠图
  走「上传 Word/PDF → AI 拆题」时，平台会自动把文档里的图抽出来挂到对应题目，
  不需要手写 images。本模板只在「由程序/脚本生成标准包」时才需要照填。

五、其它字段
  · question_type：single / multiple / judge / fill / short / essay / code
  · code 题可给 language、starter_code、test_cases（[{ "input": "3", "expected_output": "6" }]）
  · score 留空表示「分值待定」，导入后整卷满分显示为未知，不会记 0 分`

/** 下载导入 JSON 模板文件（浏览器端直接生成，不需要后端） */
export function downloadImportTemplate(filename = 'paper-template.json') {
  const blob = new Blob([IMPORT_TEMPLATE_JSON], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

let crcTableCache: Uint32Array | null = null
function crcTable(): Uint32Array {
  if (crcTableCache) return crcTableCache
  const table = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    table[n] = c >>> 0
  }
  crcTableCache = table
  return table
}

function crc32(bytes: Uint8Array): number {
  const table = crcTable()
  let crc = 0xffffffff
  for (let i = 0; i < bytes.length; i++) {
    crc = (crc >>> 8) ^ table[(crc ^ bytes[i]) & 0xff]
  }
  return (crc ^ 0xffffffff) >>> 0
}

/**
 * 把若干文本文件打成一个 zip（STORED 不压缩）。
 * 这里手写而不是引依赖：骨架只有几个文本文件，压缩与否无所谓，能少一个依赖就少一个。
 */
function buildStoredZip(files: { name: string; content: string }[]): Blob {
  const encoder = new TextEncoder()
  const localParts: Uint8Array[] = []
  const centralParts: Uint8Array[] = []
  let offset = 0
  for (const file of files) {
    const nameBytes = encoder.encode(file.name)
    const data = encoder.encode(file.content)
    const crc = crc32(data)

    const local = new Uint8Array(30 + nameBytes.length)
    const lv = new DataView(local.buffer)
    lv.setUint32(0, 0x04034b50, true)
    lv.setUint16(4, 20, true)
    lv.setUint16(6, 0x0800, true) // 文件名按 UTF-8
    lv.setUint16(8, 0, true) // 不压缩
    lv.setUint16(10, 0, true)
    lv.setUint16(12, 0x21, true) // 1980-01-01
    lv.setUint32(14, crc, true)
    lv.setUint32(18, data.length, true)
    lv.setUint32(22, data.length, true)
    lv.setUint16(26, nameBytes.length, true)
    lv.setUint16(28, 0, true)
    local.set(nameBytes, 30)
    localParts.push(local, data)

    const central = new Uint8Array(46 + nameBytes.length)
    const cv = new DataView(central.buffer)
    cv.setUint32(0, 0x02014b50, true)
    cv.setUint16(4, 20, true)
    cv.setUint16(6, 20, true)
    cv.setUint16(8, 0x0800, true)
    cv.setUint16(10, 0, true)
    cv.setUint16(12, 0, true)
    cv.setUint16(14, 0x21, true)
    cv.setUint32(16, crc, true)
    cv.setUint32(20, data.length, true)
    cv.setUint32(24, data.length, true)
    cv.setUint16(28, nameBytes.length, true)
    cv.setUint16(30, 0, true)
    cv.setUint16(32, 0, true)
    cv.setUint16(34, 0, true)
    cv.setUint16(36, 0, true)
    cv.setUint32(38, 0, true)
    cv.setUint32(42, offset, true)
    central.set(nameBytes, 46)
    centralParts.push(central)

    offset += local.length + data.length
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0)
  const end = new Uint8Array(22)
  const ev = new DataView(end.buffer)
  ev.setUint32(0, 0x06054b50, true)
  ev.setUint16(4, 0, true)
  ev.setUint16(6, 0, true)
  ev.setUint16(8, files.length, true)
  ev.setUint16(10, files.length, true)
  ev.setUint32(12, centralSize, true)
  ev.setUint32(16, offset, true)
  ev.setUint16(20, 0, true)

  return new Blob([...localParts, ...centralParts, end], { type: 'application/zip' })
}

/** 下载「标准包」骨架：paper.json + assets/放图提示 + 使用说明.txt */
export function downloadImportPackageTemplate(filename = 'paper-import-template.zip') {
  const blob = buildStoredZip([
    { name: 'paper.json', content: IMPORT_TEMPLATE_JSON },
    {
      name: 'assets/把图片放进这个文件夹.txt',
      content:
        '把题目图片放在 assets/ 目录下，文件名建议 image-1.jpg、image-2.jpg ……\n' +
        '然后在 paper.json 里用 { "asset": "assets/image-N.jpg", "index": N } 引用，\n' +
        'index 要和题干里 [[IMG:N]] 的编号一致。详见 使用说明.txt。\n'
    },
    { name: '使用说明.txt', content: IMPORT_PACKAGE_GUIDE }
  ])
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

export const assessmentApi = {
  uploadFile(file: File, source = 'assessment_upload') {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/files/upload?source=${source}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /** 从标准 JSON / 压缩包导入试卷（不走 AI 拆题） */
  importPaper(fileId: string, title?: string) {
    return request.post('/assessment/papers/import', { file_id: fileId, title })
  },

  /** 把一张卷导出成「标准包」：paper.json + assets/ 的 zip（改完可再导回来） */
  exportPaperPackage(paperId: string) {
    return request.get(`/assessment/papers/${paperId}/package-export`, { responseType: 'blob' })
  },

  createPaper(data: { file_id: string; title: string; description?: string }) {
    return request.post('/assessment/papers', data)
  },

  listPapers() {
    return request.get('/assessment/papers')
  },

  getPaper(id: string) {
    return request.get(`/assessment/papers/${id}`)
  },

  getParseStatus(id: string) {
    return request.get(`/assessment/papers/${id}/parse-status`)
  },

  reparsePaper(id: string) {
    return request.post(`/assessment/papers/${id}/reparse`)
  },

  listQuestions(id: string) {
    return request.get(`/assessment/papers/${id}/questions`)
  },

  saveQuestions(id: string, questions: any[]) {
    return request.put(`/assessment/papers/${id}/questions`, { questions })
  },

  publishPaper(
    id: string,
    data: {
      publish_target: Record<string, any>
      publish_at?: string | null
      due_at?: string | null
      time_limit_minutes?: number | null
      require_fullscreen?: boolean
      grading_preference?: { mode: string; extra?: string } | null
    }
  ) {
    return request.post(`/assessment/papers/${id}/publish`, data)
  },

  listStudentPapers() {
    return request.get('/assessment/student/papers')
  },

  getStudentQuestions(paperId: string) {
    return request.get(`/assessment/student/papers/${paperId}/questions`)
  },

  startAttempt(paperId: string) {
    return request.post(`/assessment/student/papers/${paperId}/attempts`)
  },

  runCode(attemptId: string, questionId: string, data: { code: string; stdin?: string | null }) {
    // 自测要真的编译运行，比普通请求慢得多；超时只断前端，服务端会跑完
    return request.post(
      `/assessment/student/attempts/${attemptId}/questions/${questionId}/run`,
      data,
      { timeout: 90_000 }
    )
  },

  getStudentAnswers(paperId: string) {
    return request.get(`/assessment/student/papers/${paperId}/answers`)
  },

  getStudentReview(paperId: string) {
    return request.get(`/assessment/student/papers/${paperId}/review`)
  },

  saveAnswers(attemptId: string, answers: StudentAnswerIn[]) {
    // 违规超限时后端会强制交卷，并在 data 里回传 attempt，前端据此切到已交卷态
    return request.put(`/assessment/student/attempts/${attemptId}/answers`, { answers })
  },

  submitAttempt(attemptId: string, answers: StudentAnswerIn[]) {
    // 交卷时要在服务端同步跑完所有编程题的判题：每个超时的用例都会吃满 CPU 上限，
    // 一份编程题较多的卷可能远超默认 30 秒。超时只断前端，服务端会做完结算。
    return request.post(
      `/assessment/student/attempts/${attemptId}/submit`,
      { answers },
      { timeout: 180_000 }
    )
  },

  reportBehavior(data: {
    session_id: string
    attempt_id?: string | null
    events: BehaviorEventPayload[]
  }) {
    return request.post('/assessment/student/behavior/batch', data)
  },

  listPaperAttempts(paperId: string) {
    return request.get(`/assessment/papers/${paperId}/attempts`)
  },

  exportScoreSheet(paperId: string) {
    return request.get(`/assessment/papers/${paperId}/score-sheet.pdf`, { responseType: 'blob' })
  },

  /** 学生导出自己的错题本；传 template 可自定义 JSON 模板（页眉/页脚/字段） */
  exportMyNotebook(paperId: string, template?: Record<string, any>) {
    return request.get(`/assessment/papers/${paperId}/my-notebook-export`, {
      params: template ? { template: JSON.stringify(template) } : undefined,
      responseType: 'blob'
    })
  },

  getPaperAnalytics(paperId: string) {
    return request.get(`/assessment/papers/${paperId}/analytics`)
  },

  listAttemptBehavior(
    attemptId: string,
    params?: { event_type?: string; question_id?: string; offset?: number; limit?: number }
  ) {
    return request.get(`/assessment/attempts/${attemptId}/behavior`, { params })
  },

  getAttemptInsights(attemptId: string) {
    return request.get(`/assessment/attempts/${attemptId}/insights`)
  },

  updateGradingPreference(paperId: string, gradingPreference: { mode: string; extra?: string } | null) {
    return request.put(`/assessment/papers/${paperId}/grading-preference`, {
      grading_preference: gradingPreference
    })
  },

  getClassExamAnalytics(classId: string) {
    return request.get(`/assessment/classes/${classId}/exam-analytics`)
  },

  getStudentExamHistory(classId: string, studentId: string) {
    return request.get(`/assessment/classes/${classId}/students/${studentId}/exams`)
  },

  listAttemptAnswers(attemptId: string) {
    return request.get(`/assessment/attempts/${attemptId}/answers`)
  },

  gradeAttempt(attemptId: string, grades: { question_id: string; score: number }[]) {
    return request.post(`/assessment/attempts/${attemptId}/grade`, { grades })
  },

  aiGradeAttempt(attemptId: string, data: { question_ids?: string[]; overwrite?: boolean } = {}) {
    // 主观题逐题调用模型，一整卷可能远超默认 30 秒；超时只断前端，服务端仍会写完。
    return request.post(`/assessment/attempts/${attemptId}/ai-grade`, data, { timeout: 600_000 })
  }
}