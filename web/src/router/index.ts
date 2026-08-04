import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import LoginView from '../views/common/LoginView.vue'
import NotFoundView from '../views/common/NotFoundView.vue'
import ForbiddenView from '../views/common/ForbiddenView.vue'
import ProfileView from '../views/common/ProfileView.vue'
import AnnouncementsView from '../views/common/AnnouncementsView.vue'

import DashboardView from '../views/student/DashboardView.vue'
import ChatView from '../views/student/ChatView.vue'
import CalendarView from '../views/student/CalendarView.vue'
import KnowledgeView from '../views/student/KnowledgeView.vue'
import BilibiliView from '../views/student/BilibiliView.vue'
import StudentLearningPathsView from '../views/student/LearningPathsView.vue'
import GrowthView from '../views/student/GrowthView.vue'

import WorkbenchView from '../views/teacher/WorkbenchView.vue'
import StudentsView from '../views/teacher/StudentsView.vue'
import TasksView from '../views/teacher/TasksView.vue'
import TeacherLearningPathsView from '../views/teacher/LearningPathsView.vue'
import TeacherLearningPathCreateView from '../views/teacher/LearningPathCreateView.vue'
import TeacherLearningPathStudentProgressView from '../views/teacher/LearningPathStudentProgressView.vue'
import ClassOverviewView from '../views/teacher/ClassOverviewView.vue'

import OverviewView from '../views/admin/OverviewView.vue'
import UsersView from '../views/admin/UsersView.vue'
import LlmConfigsView from '../views/admin/LlmConfigsView.vue'
import SettingsView from '../views/admin/SettingsView.vue'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { title: '用户登录', requiresAuth: false }
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: ForbiddenView,
    meta: { title: '权限不足', requiresAuth: false }
  },
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/student',
    component: MainLayout,
    meta: { requiresAuth: true, role: 'student' },
    children: [
      {
        path: 'dashboard',
        name: 'StudentDashboard',
        component: DashboardView,
        meta: { title: '我的仪表盘' }
      },
      {
        path: 'ai-chat',
        name: 'StudentChat',
        component: ChatView,
        meta: { title: 'AI 伴学助手' }
      },
      {
        path: 'calendar',
        name: 'StudentCalendar',
        component: CalendarView,
        meta: { title: '学习计划月历' }
      },
      {
        path: 'knowledge',
        name: 'StudentKnowledge',
        component: KnowledgeView,
        meta: { title: '实验室知识库' }
      },
      {
        path: 'bilibili',
        name: 'StudentBilibili',
        component: BilibiliView,
        meta: { title: 'B 站学习室' }
      },
      {
        path: 'learning-paths',
        name: 'StudentLearningPaths',
        component: StudentLearningPathsView,
        meta: { title: '我的学习路径' }
      },
      {
        path: 'growth',
        name: 'StudentGrowth',
        component: GrowthView,
        meta: { title: '成长数据全览' }
      }
    ]
  },
  {
    path: '/teacher',
    component: MainLayout,
    meta: { requiresAuth: true, role: 'teacher' },
    children: [
      {
        path: 'workbench',
        name: 'TeacherWorkbench',
        component: WorkbenchView,
        meta: { title: '教学工作台' }
      },
      {
        path: 'students',
        name: 'TeacherStudents',
        component: StudentsView,
        meta: { title: '我的指导学生' }
      },
      {
        path: 'tasks',
        name: 'TeacherTasks',
        component: TasksView,
        meta: { title: '学习任务发布' }
      },
      {
        path: 'learning-paths',
        name: 'TeacherLearningPaths',
        component: TeacherLearningPathsView,
        meta: { title: '学习路径任务' }
      },
      {
        path: 'learning-paths/new',
        name: 'TeacherLearningPathCreate',
        component: TeacherLearningPathCreateView,
        meta: { title: '布置学习路径任务' }
      },
      {
        path: 'learning-paths/:taskId/students/:studentId',
        name: 'TeacherLearningPathStudentProgress',
        component: TeacherLearningPathStudentProgressView,
        meta: { title: '学生路径进度' }
      },
      {
        path: 'classes',
        name: 'TeacherClasses',
        component: ClassOverviewView,
        meta: { title: '班级学情记忆看板' }
      },
      {
        path: 'announcements',
        name: 'TeacherAnnouncements',
        component: AnnouncementsView,
        meta: { title: '公告发布' }
      }
    ]
  },
  {
    path: '/admin',
    component: MainLayout,
    meta: { requiresAuth: true, role: 'admin' },
    children: [
      {
        path: 'overview',
        name: 'AdminOverview',
        component: OverviewView,
        meta: { title: '管理面板概览' }
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: UsersView,
        meta: { title: '系统用户管理' }
      },
      {
        path: 'llm-configs',
        name: 'AdminLlmConfigs',
        component: LlmConfigsView,
        meta: { title: '模型通道管理' }
      },
      {
        path: 'settings',
        name: 'AdminSettings',
        component: SettingsView,
        meta: { title: '全局系统设置' }
      },
      {
        path: 'announcements',
        name: 'AdminAnnouncements',
        component: AnnouncementsView,
        meta: { title: '公告发布' }
      }
    ]
  },
  {
    path: '/common',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '/profile',
        name: 'Profile',
        component: ProfileView,
        meta: { title: '个人设置' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFoundView,
    meta: { title: '页面未找到', requiresAuth: false }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - AI伴学协同平台`
  }

  const token = localStorage.getItem('sp_token')
  const userRole = localStorage.getItem('sp_role')

  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!token) {
      next('/login')
      return
    }

    const requiredRole = to.matched.find(record => record.meta.role)?.meta.role
    if (requiredRole && requiredRole !== userRole) {
      next('/403')
      return
    }

    next()
    return
  }

  if (to.path === '/login' && token && userRole) {
    if (userRole === 'admin') {
      next('/admin/overview')
    } else if (userRole === 'teacher') {
      next('/teacher/workbench')
    } else {
      next('/student/dashboard')
    }
    return
  }

  next()
})

export default router
