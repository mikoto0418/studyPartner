const MEMORY_CATEGORY_LABELS: Record<string, string> = {
  goal: '学习目标',
  interest_area: '兴趣方向',
  learning_preference: '学习偏好',
  study_habit: '学习习惯',
  weakness: '薄弱项',
  strength: '优势能力',
  knowledge_gap: '知识缺口',
  learning_style: '学习方式',
  resource_preference: '资源偏好',
  communication_style: '沟通偏好',
  motivation: '学习动机',
  emotion: '情绪状态',
  schedule: '时间安排',
  plan: '学习计划',
  task: '学习任务',
  todo: '待办事项',
  progress: '学习进度',
  risk: '风险关注',
  concern: '关注事项',
  challenge: '学习挑战',
  concept: '知识概念',
  skill: '技能掌握',
  project: '项目方向',
  research_interest: '研究兴趣',
  profile: '学生画像',
  background: '基础背景',
  preference: '偏好信息',
  habit: '习惯特征',
  short_term: '短期记忆',
  long_term: '长期记忆',
  unknown: '未分类'
}

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export const memoryCategoryLabel = (category?: string | null) => {
  if (!category) return '未分类'
  const normalized = category.trim()
  if (!normalized) return '未分类'
  return MEMORY_CATEGORY_LABELS[normalized] || '其他分类'
}

export const localizeMemorySummaryText = (value?: string | null) => {
  if (!value) return '暂无记忆聚合摘要。'

  let localized = value

  Object.entries(MEMORY_CATEGORY_LABELS)
    .sort(([left], [right]) => right.length - left.length)
    .forEach(([key, label]) => {
      localized = localized.replace(new RegExp(`\\b${escapeRegExp(key)}\\b`, 'g'), label)
    })

  return localized.replace(/\b[a-z][a-z0-9_]*(?=\(\d+\))/gi, '其他分类')
}
