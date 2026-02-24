import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  root: '.',
  publicDir: 'public',
  resolve: {
    preserveSymlinks: false,
  },
  server: {
    port: 3000,
    fs: {
      allow: ['.', '../../maps'],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8432',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'build',
    emptyOutDir: true,
  },
});
