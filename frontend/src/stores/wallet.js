import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from './auth'
import router from '@/router'

export const useWalletStore = defineStore('wallet', () => {
  const me = ref({})
  const users = ref([])
  const history = ref([])
  const loading = ref(false)
  const lastError = ref('')

  async function refresh() {
    const auth = useAuthStore()
    if (!auth.userToken) return
    loading.value = true
    lastError.value = ''
    try {
      const [m, u, h] = await Promise.all([
        apiCall('/me', { token: auth.userToken }),
        apiCall('/users', { token: auth.userToken }),
        apiCall('/history', { token: auth.userToken })
      ])
      me.value = m
      users.value = u
      history.value = h
    } catch (e) {
      if (/401|Token|invalid/i.test(String(e.message))) {
        auth.logoutUser()
        reset()
        router.push({ name: 'login' })
      } else {
        lastError.value = e.message
      }
    } finally {
      loading.value = false
    }
  }

  function reset() {
    me.value = {}
    users.value = []
    history.value = []
  }

  return { me, users, history, loading, lastError, refresh, reset }
})
