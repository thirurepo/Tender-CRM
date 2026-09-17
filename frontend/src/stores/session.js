import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import router from '@/router'
import { ref, computed } from 'vue'

export const sessionStore = defineStore('crm-session', () => {
  function sessionUser() {
    let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
    let _sessionUser = cookies.get('user_id')
    if (_sessionUser === 'Guest') {
      _sessionUser = null
    }
    return _sessionUser
  }

  let user = ref(sessionUser())
  const isLoggedIn = computed(() => !!user.value)

  const login = createResource({
    url: 'login',
    onError() {
      throw new Error(__('Invalid Email or Password'))
    },
    onSuccess() {
      user.value = sessionUser()
      login.reset()
      router.replace({ path: '/' })
    },
  })

  const logout = createResource({
    url: 'logout',
    onSuccess() {
      user.value = null
      // Third and last copy of upstream's hardcoded '/crm' in this fork (the
      // other two were the router's history base and its own login redirect).
      // Logging out of the TSI app has to send you back to the TSI app.
      window.location.href = '/login?redirect-to=/tsi-crm'
    },
  })

  return {
    user,
    isLoggedIn,
    login,
    logout,
  }
})
