/**
 * Color-scheme toggle shown in the menubar.
 *
 * A PrimeReact SelectButton offering System / Light / Dark, bound to ``useTheme``:
 * the selected value is the persisted mode, and picking one calls
 * ``setTheme`` (which writes the ``theme`` localStorage key and applies the
 * resolved ``data-theme`` attribute — see ``useTheme.ts``).
 */
import { SelectButton } from 'primereact/selectbutton'
import { useTheme, type ThemeMode } from './useTheme'

/** The three selectable theme modes, in display order. */
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