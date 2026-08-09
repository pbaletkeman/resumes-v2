import { SelectButton } from 'primereact/selectbutton'
import { useTheme, type ThemeMode } from './useTheme'

const OPTIONS: { label: string; value: ThemeMode }[] = [
  { label: 'System', value: 'system' },
  { label: 'Light', value: 'light' },
  { label: 'Dark', value: 'dark' },
]

function ThemeToggle() {
  const { mode, setTheme } = useTheme()

  return (
    <SelectButton
      value={mode}
      onChange={(e) => setTheme(e.value as ThemeMode)}
      options={OPTIONS}
      aria-label="Color scheme"
    />
  )
}

export default ThemeToggle