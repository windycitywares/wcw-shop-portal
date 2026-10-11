import type { NextConfig } from "next";

const isStaticExport = process.env.NEXT_OUTPUT === "export";

// Basic hardening for every page. (Not applied to `output: "export"` builds — set
// these in .htaccess there.)
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000" },
];

const nextConfig: NextConfig = {
  // "standalone" = small Node server (cPanel "Setup Node.js App");
  // "export" = plain HTML files for static-only hosting (no SSR, no on-demand pages).
  output: isStaticExport ? "export" : "standalone",
  poweredByHeader: false,
  ...(isStaticExport ? {} : { headers: async () => [{ source: "/:path*", headers: securityHeaders }] }),
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
