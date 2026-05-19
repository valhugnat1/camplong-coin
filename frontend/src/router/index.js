import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  // ─── User
  { path: '/', redirect: '/wallet' },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guest: true }
  },
  {
    path: '/wallet',
    name: 'wallet',
    component: () => import('@/views/WalletView.vue'),
    meta: { needsUser: true }
  },
  {
    path: '/paris',
    name: 'paris',
    component: () => import('@/views/ParisView.vue'),
    meta: { needsUser: true }
  },
  {
    path: '/casino',
    name: 'casino',
    component: () => import('@/views/CasinoView.vue'),
    meta: { needsUser: true }
  },
  {
    path: '/milk',
    name: 'milk',
    component: () => import('@/views/MilkView.vue'),
    meta: { needsUser: true }
  },

  // ─── Admin
  {
    path: '/admin/login',
    name: 'admin-login',
    component: () => import('@/views/admin/AdminLoginView.vue'),
    meta: { guest: true }
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/admin/AdminView.vue'),
    meta: { needsAdmin: true }
  },

  // Fallback
  { path: '/:pathMatch(.*)*', redirect: '/wallet' }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.needsUser && !auth.userToken) return { name: 'login' }
  if (to.meta.needsAdmin && !auth.adminToken) return { name: 'admin-login' }
  return true
})

export default router
