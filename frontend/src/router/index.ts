import { createRouter, createWebHistory } from 'vue-router'

import GeneratorView from '../views/GeneratorView.vue'
import { hasStoredToken } from '../api'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'generator',
      component: GeneratorView,
      meta: { requiresAuth: true, keepAlive: true },
    },
    {
      path: '/community',
      name: 'community',
      component: () => import('../views/CommunityView.vue'),
    },
    {
      path: '/works',
      name: 'works',
      component: () => import('../views/MyWorksView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
  ],
})

router.beforeEach((to) => {
  const authenticated = hasStoredToken()
  if (to.meta.requiresAuth && !authenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && authenticated) return { name: 'generator' }
  return true
})

export default router
