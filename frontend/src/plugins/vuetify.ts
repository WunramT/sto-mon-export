import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import { de } from 'vuetify/locale'

export default createVuetify({
  locale: { locale: 'de', messages: { de } },
  icons: { defaultSet: 'mdi' },
  defaults: {
    VBtn: { variant: 'flat', rounded: 'md', style: 'text-transform:none;letter-spacing:0' },
    VTextField: { variant: 'outlined', density: 'compact', hideDetails: 'auto', color: 'primary' },
    VTextarea: { variant: 'outlined', density: 'compact', hideDetails: 'auto', color: 'primary' },
    VSelect: { variant: 'outlined', density: 'compact', hideDetails: 'auto', color: 'primary' },
    VAutocomplete: { variant: 'outlined', density: 'compact', hideDetails: 'auto', color: 'primary' },
    VCard: { rounded: 'lg' },
    VChip: { rounded: 'md' },
    VTooltip: { location: 'top', openDelay: 400 },
  },
  theme: {
    defaultTheme: 'hell',
    themes: {
      hell: {
        dark: false,
        colors: {
          primary: '#ce003c',
          secondary: '#3c4649',
          background: '#f4f5f7',
          surface: '#ffffff',
          'surface-variant': '#eef0f3',
          error: '#c62828',
          info: '#1f6fb2',
          success: '#1e7d4f',
          warning: '#b86e00',
          'on-primary': '#ffffff',
          'on-secondary': '#ffffff',
        },
      },
    },
  },
})
