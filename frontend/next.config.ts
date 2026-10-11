import type { NextConfig } from "next";

const isStaticExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = {
  // "standalone" = small Node server (cPanel "Setup Node.js App");
  // "export" = plain HTML files for static-only hosting (no SSR, no on-demand pages).
  output: isStaticExport ? "export" : "standalone",
  poweredByHeader: false,
  images: {
    unoptimized: isStaticExport,
    remotePatterns: [
      { protocol: "https", hostname: "i.etsystatic.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
      { protocol: "https", hostname: "images-na.ssl-images-amazon.com" },
    ],
  },
};

export default nextConfig;
