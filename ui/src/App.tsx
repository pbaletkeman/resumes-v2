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

const NAV_ITEMS = [
  { label: 'Run', icon: 'pi pi-play', to: '/' },
  { label: 'Files', icon: 'pi pi-folder', to: '/files' },
  { label: 'Models', icon: 'pi pi-cog', to: '/models' },
]

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