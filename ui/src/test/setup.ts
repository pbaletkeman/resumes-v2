/**
 * Vitest setup: register the jest-dom matchers.
 *
 * Loaded once per test run via vite.config.ts ``test.setupFiles``. Importing
 * ``@testing-library/jest-dom/vitest`` extends Vitest's expect with the
 * jest-dom matchers (``toBeInTheDocument``, ``toBeDisabled``, ...) that the
 * component tests rely on.
 */
import '@testing-library/jest-dom/vitest'