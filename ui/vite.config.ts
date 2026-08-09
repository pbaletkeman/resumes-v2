import postcss from 'postcss'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const darkThemeScope = "html[data-theme='dark']"

function scopeDarkTheme(code: string): string {
  const root = postcss.parse(code)
  root.walkRules((rule) => {
    if (!rule.parent || rule.parent.type !== 'atrule' || rule.parent.name !== 'keyframes') {
      rule.selector = rule.selector
        .split(',')
        .map((selector) => {
          const sel = selector.trim()
          return sel === ':root' ? darkThemeScope : `${darkThemeScope} ${sel}`
        })
        .join(', ')
    }
  })
  return root.toString()
}

const scopeDarkThemeCss = (): Plugin => ({
  name: 'scope-dark-theme',
  enforce: 'pre',
  transform(code, id) {
    if (id.includes('lara-dark-blue/theme.css')) {
      return { code: scopeDarkTheme(code), map: null }
    }
    return null
  },
})

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), scopeDarkThemeCss()],
})