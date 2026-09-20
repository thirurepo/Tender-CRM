<template>
  <div class="flex h-screen w-screen">
    <!-- The wrapper is what the notifications panel positions itself against
         (it is absolutely placed at left: 100%). TsiSidebar scrolls
         (overflow-y: auto), which would clip a panel mounted inside it, so the
         panel lives beside it instead. -->
    <div class="relative shrink-0">
      <TsiSidebar />
      <Notifications />
    </div>
    <div class="flex-1 flex flex-col h-full overflow-auto bg-surface-base">
      <AppHeader />
      <slot />
    </div>
    <GlobalModals />
    <!-- Mounted here, not in TsiSidebar: AppSidebar used to own this dialog,
         and replacing it with TsiSidebar left nothing on desktop to open it
         (UserDropdown, Templates' "manage" link, document.js all still set
         showSettings and expect a dialog to be listening). -->
    <Settings />
  </div>
</template>
<script setup>
import TsiSidebar from '@/components/Layouts/TsiSidebar.vue'
import AppHeader from '@/components/Layouts/AppHeader.vue'
import Notifications from '@/components/Notifications.vue'
import GlobalModals from '@/components/Modals/GlobalModals.vue'
import Settings from '@/components/Settings/Settings.vue'
</script>
