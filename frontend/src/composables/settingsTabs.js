/**
 * Tender CRM — shared settings tab list.
 *
 * Extracted from Settings.vue so the TSI sidebar can list the same settings
 * pages the dialog does. See useSettingsTabs() below.
 */
import { Avatar } from 'frappe-ui'
import { markRaw, computed, h } from 'vue'
import LucideLayoutDashboard from '~icons/lucide/layout-dashboard'
import LucideNetwork from '~icons/lucide/network'
import MonitorCogIcon from '~icons/lucide/monitor-cog'
import LucideTextCursorInput from '~icons/lucide/text-cursor-input'
import SlidersIcon from '@/components/Icons/SlidersIcon.vue'
import SparkleIcon from '@/components/Icons/SparkleIcon.vue'
import WhatsAppIcon from '@/components/Icons/WhatsAppIcon.vue'
import ERPNextIcon from '@/components/Icons/ERPNextIcon.vue'
import PhoneIcon from '@/components/Icons/PhoneIcon.vue'
import Email2Icon from '@/components/Icons/Email2Icon.vue'
import EmailTemplateIcon from '@/components/Icons/EmailTemplateIcon.vue'
import SettingsIcon from '@/components/Icons/SettingsIcon.vue'
import SettingsIcon2 from '@/components/Icons/SettingsIcon2.vue'
import Users from '@/components/Settings/Users.vue'
import Hierarchy from '@/components/Settings/Hierarchy/Hierarchy.vue'
import InviteUserPage from '@/components/Settings/InviteUserPage.vue'
import ProfilePage from '@/components/Settings/Profile/ProfilePage.vue'
import PreferencesSettings from '@/components/Settings/PreferencesSettings.vue'
import WhatsAppSettings from '@/components/Settings/WhatsAppSettings.vue'
import ERPNextSettings from '@/components/Settings/ERPNextSettings.vue'
import LeadSyncSourcePage from '@/components/Settings/LeadSyncing/LeadSyncSourcePage.vue'
import DefaultsSettings from '@/components/Settings/DefaultsSettings.vue'
import BrandSettings from '@/components/Settings/BrandSettings.vue'
import HomeActions from '@/components/Settings/HomeActions.vue'
import FormsSettings from '@/components/Settings/Forms/FormsSettings.vue'
import GeneralSettings from '@/components/Settings/GeneralSettings.vue'
import DashboardSettings from '@/components/Settings/DashboardSettings.vue'
import EmailTemplatePage from '@/components/Settings/EmailTemplate/EmailTemplatePage.vue'
import TelephonyPage from '@/components/Settings/Telephony/TelephonyPage.vue'
import EmailConfig from '@/components/Settings/EmailConfig.vue'
import { usersStore } from '@/stores/users'
import { isWhatsappInstalled } from '@/composables/whatsapp'
import AssignmentRulePage from '@/components/Settings/AssignmentRules/AssignmentRulePage.vue'
import ShieldCheck from '~icons/lucide/shield-check'
import SlaConfig from '@/components/Settings/Sla/SlaConfig.vue'

/**
 * The settings navigation, as data: groups of pages, each with a label, icon
 * and component, already filtered by permission (manager-only sections drop
 * out for everyone else).
 *
 * Lives outside Settings.vue because two things render it: the Settings
 * dialog's own left rail, and the "Settings" group in the TSI sidebar
 * (TsiSidebar.vue). Keeping one list means a page added or permission-gated
 * here shows up — or disappears — in both places at once, instead of the
 * sidebar linking to a label the dialog no longer has.
 */
export function useSettingsTabs() {
  const { isManager, getUser } = usersStore()

  const user = computed(() => getUser() || {})

  return computed(() => {
    let _tabs = [
      {
        label: __('User Configuration'),
        items: [
          {
            label: __('Profile'),
            icon: () =>
              h(Avatar, {
                size: 'xs',
                label: user.value.full_name,
                image: user.value.user_image,
              }),
            component: markRaw(ProfilePage),
          },
          {
            label: __('Preferences'),
            icon: SlidersIcon,
            component: markRaw(PreferencesSettings),
          },
        ],
      },
      {
        label: __('System Configuration'),
        items: [
          {
            label: __('General'),
            component: markRaw(GeneralSettings),
            icon: SettingsIcon,
          },
          {
            label: __('Dashboard'),
            component: markRaw(DashboardSettings),
            icon: LucideLayoutDashboard,
          },
          {
            label: __('Defaults'),
            component: markRaw(DefaultsSettings),
            icon: MonitorCogIcon,
          },
          {
            label: __('Brand'),
            icon: SparkleIcon,
            component: markRaw(BrandSettings),
          },
        ],
        condition: () => isManager(),
      },
      {
        label: __('User Management'),
        items: [
          {
            label: __('Users'),
            icon: 'user',
            component: markRaw(Users),
            condition: () => isManager(),
          },
          {
            label: __('Invite User'),
            icon: 'user-plus',
            component: markRaw(InviteUserPage),
            condition: () => isManager(),
          },
          {
            label: __('Sales Hierarchy'),
            icon: LucideNetwork,
            component: markRaw(Hierarchy),
            condition: () => isManager(),
          },
        ],
        condition: () => isManager(),
      },
      {
        label: __('Email'),
        items: [
          {
            label: __('Accounts'),
            icon: Email2Icon,
            component: markRaw(EmailConfig),
            condition: () => isManager(),
          },
          {
            label: __('Templates'),
            icon: EmailTemplateIcon,
            component: markRaw(EmailTemplatePage),
          },
        ],
      },
      {
        label: __('Automation & Rules'),
        items: [
          {
            label: __('Assignment Rules'),
            icon: markRaw(h(SettingsIcon2, { class: 'rotate-90' })),
            component: markRaw(AssignmentRulePage),
          },
          {
            label: __('SLA Policies'),
            icon: markRaw(h(ShieldCheck)),
            component: markRaw(SlaConfig),
          },
          {
            label: __('Forms'),
            component: markRaw(FormsSettings),
            icon: markRaw(LucideTextCursorInput),
          },
        ],
        condition: () => isManager(),
      },
      {
        label: __('Customization'),
        items: [
          {
            label: __('Home Actions'),
            component: markRaw(HomeActions),
            icon: 'house',
          },
        ],
        condition: () => isManager(),
      },
      {
        label: __('Integrations', null, 'FCRM'),
        items: [
          {
            label: __('Telephony'),
            icon: PhoneIcon,
            component: markRaw(TelephonyPage),
          },
          {
            label: __('WhatsApp'),
            icon: WhatsAppIcon,
            component: markRaw(WhatsAppSettings),
            condition: () => isWhatsappInstalled.value && isManager(),
          },
          {
            label: __('ERPNext'),
            icon: ERPNextIcon,
            component: markRaw(ERPNextSettings),
            condition: () => isManager(),
          },
          {
            label: __('Lead Syncing'),
            icon: 'refresh-cw',
            component: markRaw(LeadSyncSourcePage),
            condition: () => isManager(),
          },
        ],
      },
    ]

    return _tabs.filter((tab) => {
      if (tab.condition && !tab.condition()) return false
      if (tab.items) {
        tab.items = tab.items.filter((item) => {
          if (item.condition && !item.condition()) return false
          return true
        })
      }
      return true
    })
  })
}
