import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const userToken = ref(localStorage.getItem('token') || '')
  const adminToken = ref(localStorage.getItem('admin_token') || '')

  function setUserToken(t) {
    userToken.value = t
    if (t) localStorage.setItem('token', t)
    else localStorage.removeItem('token')
  }

  function setAdminToken(t) {
    adminToken.value = t
    if (t) localStorage.setItem('admin_token', t)
    else localStorage.removeItem('admin_token')
  }

  function logoutUser() {
    setUserToken('')
  }

  function logoutAdmin() {
    setAdminToken('')
  }

  return { userToken, adminToken, setUserToken, setAdminToken, logoutUser, logoutAdmin }
})
