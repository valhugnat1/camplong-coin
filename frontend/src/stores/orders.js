import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from './auth'

export const useOrdersStore = defineStore('orders', () => {
  const orders = ref([])
  const loading = ref(false)
  const lastError = ref('')

  const pendingCount = computed(() =>
    orders.value.filter((o) => o.status === 'pending').length
  )

  async function load(status = 'all') {
    const auth = useAuthStore()
    if (!auth.adminToken) return
    loading.value = true
    lastError.value = ''
    try {
      orders.value = await apiCall(`/admin/orders?status=${status}`, {
        token: auth.adminToken
      })
    } catch (e) {
      lastError.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function update(id, payload) {
    const auth = useAuthStore()
    const updated = await apiCall(`/admin/orders/${id}`, {
      method: 'PATCH',
      token: auth.adminToken,
      body: JSON.stringify(payload)
    })
    const idx = orders.value.findIndex((o) => o.id === id)
    if (idx >= 0) orders.value[idx] = updated
    return updated
  }

  async function remove(id) {
    const auth = useAuthStore()
    await apiCall(`/admin/orders/${id}`, {
      method: 'DELETE',
      token: auth.adminToken
    })
    orders.value = orders.value.filter((o) => o.id !== id)
  }

  return { orders, loading, lastError, pendingCount, load, update, remove }
})
