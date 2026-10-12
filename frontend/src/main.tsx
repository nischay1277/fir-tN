import '@mantine/core/styles.css'
import './styles.css'
import { createTheme, MantineProvider } from '@mantine/core'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'

const theme = createTheme({
  fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  headings: {
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontWeight: '700',
  },
  defaultRadius: 'md',
  primaryColor: 'civic',
  colors: {
    civic: ['#edf6f6', '#d8e9e9', '#b5d5d6', '#8cbdc0', '#66a5aa', '#478d93', '#32757c', '#205e66', '#164b54', '#093a43'],
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme}>
      <App />
    </MantineProvider>
  </StrictMode>,
)
