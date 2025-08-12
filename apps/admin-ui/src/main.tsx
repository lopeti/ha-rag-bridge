import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './lib/i18n'
import App from './App.tsx'

// Clear old cached data on version mismatch (only during builds)
const APP_VERSION = '1.0.0'; // Manually increment when needed
const STORED_VERSION = localStorage.getItem('app_version');
if (STORED_VERSION !== APP_VERSION) {
  localStorage.clear();
  sessionStorage.clear();
  localStorage.setItem('app_version', APP_VERSION);
  console.log('🧹 Cache cleared due to version change: ' + STORED_VERSION + ' → ' + APP_VERSION);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
