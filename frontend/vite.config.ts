import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND_URL = process.env.VITE_API_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    // Permit Arena's per-session preview host; Vite already allows localhost.
    allowedHosts: ['.e2b.app'],
    proxy: {
      // The browser talks to the dev server same-origin; Vite forwards /api
      // to the FastAPI backend. This keeps the app working when the page is
      // opened from a different host (e.g. a remote preview) and avoids CORS.
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
});
