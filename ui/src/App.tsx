/**
 * App shell and routing tree.
 *
 * Nested render tree, outer to inner:
 *
 *   1. QueryClientProvider - one React Query client shared by every page.
 *   2. BrowserRouter       - client-side routing.
 *   3. ToastProvider       - global toast context used by Run / Files pages.
 *   4. Routes              - ``Shell`` is the layout route (Menubar nav +
 *      ThemeToggle + `<Outlet />`); its children map URLs to pages:
 *        index   "/"        -> RunPage
 *        /files             -> FilesPage
 *        /models            -> ModelsPage
 *
 * ``NAV_ITEMS`` drives the Menubar entries. Each entry renders a ``NavLink``
 * (so the active item is highlighted via PrimeReact's menuitem-link-active
 * class); ``end`` is set only for "/" so the other routes highlight their
 * own path instead of matching the root.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Menubar } from 'primereact/menubar'
import type { MenuItem } from 'primereact/menuitem'
import { BrowserRouter, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import FilesPage from './pages/FilesPage'
import ModelsPage from './pages/ModelsPage'
import RunPage from './pages/RunPage'
import ThemeToggle from './theme/ThemeToggle'
import ToastProvider from './toast/ToastProvider'

const queryClient = new QueryClient()

/** Top navigation entries: label + icon + route, in menubar order. */
const NAV_ITEMS = [
  { label: 'Run', icon: 'pi pi-play', to: '/' },
  { label: 'Files', icon: 'pi pi-folder', to: '/files' },
  { label: 'Models', icon: 'pi pi-cog', to: '/models' },
]

/**
 * Layout shell: a top menubar (brand, nav links, theme toggle) around the
 * routed page content. Rendered as the parent route; the active page appears
 * in the ``<Outlet />``.
 */
function Shell() {
  const model: MenuItem[] = NAV_ITEMS.map((entry) => ({
    label: entry.label,
    icon: entry.icon,
    template: () => (
      <NavLink
        to={entry.to}
        end={entry.to === '/'}
        className={({ isActive }) =>
          `p-menuitem-link${isActive ? ' p-menuitem-link-active' : ''}`
        }
      >
        <span className={`${entry.icon} p-menuitem-icon`} />
        <span className="p-menuitem-text">{entry.label}</span>
      </NavLink>
    ),
  }))

  return (
    <div className="app-shell">
      <Menubar
        model={model}
        start={
          <span className="app-brand">
            <i className="pi pi-briefcase" />
            Resume Optimizer
          </span>
        }
        end={<ThemeToggle />}
      />
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}

/**
 * Root component: wires the global providers and the route tree described in
 * the module docstring.
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<RunPage />} />
              <Route path="/files" element={<FilesPage />} />
              <Route path="/models" element={<ModelsPage />} />
            </Route>
          </Routes>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App