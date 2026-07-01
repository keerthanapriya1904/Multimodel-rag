// vite.config.js
// Tells Vite to use the React plugin so JSX works
// Sets the dev server to port 5173 (default)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173
  }
})
