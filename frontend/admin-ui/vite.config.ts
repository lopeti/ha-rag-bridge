import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/admin': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  base: '/admin/ui/', // Set base URL for assets
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        // Force new filename on each build for cache busting
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name?.split('.') || [];
          const ext = info[info.length - 1];
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext)) {
            return `assets/[name]-[hash][extname]`;
          }
          // For CSS and JS, include timestamp for better cache busting
          const timestamp = Date.now();
          return `assets/[name]-${timestamp}-[hash][extname]`;
        },
        entryFileNames: () => {
          const timestamp = Date.now();
          return `assets/[name]-${timestamp}-[hash].js`;
        }
      }
    }
  },
})