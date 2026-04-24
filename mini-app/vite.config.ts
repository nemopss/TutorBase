import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: apiProxyTarget,
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
  };
});
