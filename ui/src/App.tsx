import { Button } from 'primereact/button'
import ThemeToggle from './theme/ThemeToggle'

function App() {
  return (
    <main>
      <h1>Resume Optimizer</h1>
      <ThemeToggle />
      <Button label="Primary" />
      <Button label="Secondary" severity="secondary" />
    </main>
  )
}

export default App