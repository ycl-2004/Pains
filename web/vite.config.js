import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Relative base so the build works from any static host path (Azure Static Web Apps, GitHub Pages).
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
})
