import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React libraries
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          // Ant Design (largest dependency)
          antd: ["antd", "@ant-design/icons"],
          // Data fetching
          query: ["@tanstack/react-query"],
          // i18n
          i18n: ["i18next", "react-i18next"],
          // Date handling
          dayjs: ["dayjs"],
        },
      },
    },
  },
});
