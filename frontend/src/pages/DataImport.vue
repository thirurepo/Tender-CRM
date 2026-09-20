<template>
  <DataImport
    :doctype="route.params.doctype"
    :importName="route.params.importName"
    :doctypeMap="doctypeMap"
  />
</template>

<script setup>
import { usePageMeta } from 'frappe-ui'
import { DataImport } from 'frappe-ui/frappe'
import { useRoute } from 'vue-router'
import router from '@/router'

const route = useRoute()

// frappe-ui's import wizard follows listRoute/pageRoute with a full page load
// (window.location.href), which bypasses vue-router and so its base path. They
// must therefore carry the app prefix themselves. Read it off the router rather
// than spelling it out, so it cannot drift from createWebHistory() in router.js
// — a hardcoded '/crm' here once sent users out of this UI into stock CRM.
const base = router.options.history.base

const doctypeMap = {
  'CRM Lead': {
    title: 'Leads',
    listRoute: `${base}/leads`,
    pageRoute: `${base}/leads/docname`,
  },
  'CRM Deal': {
    title: 'Deals',
    listRoute: `${base}/deals`,
    pageRoute: `${base}/deals/docname`,
  },
  Contact: {
    title: 'Contacts',
    listRoute: `${base}/contacts`,
    pageRoute: `${base}/contacts/docname`,
  },
  'CRM Task': {
    title: 'Tasks',
    listRoute: `${base}/tasks`,
  },
  'CRM Organization': {
    title: 'Organizations',
    listRoute: `${base}/organizations`,
    pageRoute: `${base}/organizations/docname`,
  },
  'CRM Call Log': {
    title: 'Call Log',
    listRoute: `${base}/call-logs`,
  },
}

usePageMeta(() => {
  return {
    title: __('Data Import'),
  }
})
</script>
