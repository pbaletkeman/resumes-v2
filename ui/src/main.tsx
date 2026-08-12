/**
 * Entry point: mount React into ``#root`` on top of the PrimeReact styling.
 *
 * The CSS imports are the PrimeReact dependency: the light and dark Lara theme
 * stylesheets, the base components stylesheet, the primeicons icon font, and
 * the app's own global stylesheet (index.css). The dark theme stylesheet is
 * scoped to ``html[data-theme='dark']`` by vite.config.ts, so switching the
 * ``data-theme`` attribute at runtime (see ``theme/useTheme.ts``) flips between
 * the two. These imports must stay before the render so the styles are in place
 * on first paint.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'primereact/resources/themes/lara-light-blue/theme.css'
import 'primereact/resources/themes/lara-dark-blue/theme.css'
import 'primereact/resources/primereact.min.css'
import 'primeicons/primeicons.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)