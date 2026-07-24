import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["rick-mark.svg"],
      manifest: {
        name: "Rick Walking Tours",
        short_name: "Rick",
        description: "Create and listen to self-guided walking tours.",
        theme_color: "#f4f0e8",
        background_color: "#f4f0e8",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/rick-mark.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable"
          }
        ]
      },
      devOptions: {
        enabled: true
      }
    })
  ]
});
