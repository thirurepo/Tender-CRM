<template>
  <Dialog
    v-model:open="showSettings"
    :size="'5xl'"
    :disableOutsideClickToClose="disableSettingModalOutsideClick"
    @close="activeSettingsPage = ''"
  >
    <template #body>
      <div class="flex h-[calc(100vh_-_8rem)] bg-surface-gray-1">
        <div
          class="flex flex-col m-1 rounded-l-lg w-56 shrink-0 bg-surface-gray-1 overflow-y-auto"
        >
          <template v-for="(tab, i) in tabs" :key="tab.label">
            <div v-if="!tab.hideLabel && i != 0" class="mx-1 mb-0.5 mt-[5px]" />
            <div
              v-if="!tab.hideLabel"
              class="h-7.5 px-2 py-[7px] my-[3px] flex cursor-pointer gap-1.5 text-xs-medium text-ink-gray-5 transition-all duration-300 ease-in-out sticky top-0 z-10 bg-surface-gray-1"
            >
              <span>{{ __(tab.label) }}</span>
            </div>
            <nav class="space-y-[3px] px-1">
              <SidebarItem
                v-for="item in tab.items"
                :key="item.label"
                :label="__(item.label)"
                :active="activeTab?.label == item.label"
                class="w-full"
                :class="
                  activeTab?.label != item.label && 'hover:!bg-surface-gray-3'
                "
                @click="activeSettingsPage = item.label"
              >
                <template #prefix>
                  <Icon :icon="item.icon" class="size-4 text-ink-gray-7" />
                </template>
              </SidebarItem>
            </nav>
          </template>
        </div>
        <div
          class="flex flex-col flex-1 overflow-y-auto bg-surface-elevation-2"
        >
          <component :is="activeTab.component" v-if="activeTab" />
        </div>
      </div>
    </template>
  </Dialog>
</template>
<script setup>
import Icon from '@/components/Icon.vue'
import {
  showSettings,
  activeSettingsPage,
  disableSettingModalOutsideClick,
} from '@/composables/settings'
import { useSettingsTabs } from '@/composables/settingsTabs'
import { Dialog, SidebarItem } from 'frappe-ui'
import { ref, watch } from 'vue'

const tabs = useSettingsTabs()

const activeTab = ref(tabs.value[0].items[0])

function setActiveTab(tabName) {
  activeTab.value =
    (tabName &&
      tabs.value
        .map((tab) => tab.items)
        .flat()
        .find((tab) => tab.label === tabName)) ||
    tabs.value[0].items[0]
}

watch(activeSettingsPage, (activePage) => setActiveTab(activePage))
</script>
