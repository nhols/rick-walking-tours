import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["rick-mark.svg", "rick-mark-180.png"],
      manifest: {
        name: "Rick Walking Tours",
        short_name: "Rick",
        description: "Create and listen to self-guided walking tours.",
        theme_color: "#e6323b",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        icons: [
          {
            src: "/rick-mark-192.png",
            sizes: "192x192",
            type: "image/png"
          },
          {
            src: "/rick-mark-512.png",
            sizes: "512x512",
            type: "image/png"
          },
          {
            src: "/rick-mark.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "maskable"
          }
        ]
      },
      devOptions: {
        enabled: true
      }
    })
  ]
});
