import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, proxy: { '/v1': 'http://127.0.0.1:8000', '/healthz': 'http://127.0.0.1:8000' } },
  build: { outDir: path.resolve(projectDir, '../src/chrono_architect/static'), emptyOutDir: true },
});
