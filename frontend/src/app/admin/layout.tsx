import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/Providers";
import { AdminShell } from "@/components/admin/AdminShell";
import { site } from "@/lib/site";
import { themeBootScript } from "@/lib/themes";
import { adminBody, adminDisplay, body, display } from "../fonts";
import "../globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: `Admin | ${site.name}`, template: `%s | Admin | ${site.name}` },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { themeColor: "#f4f5fa", width: "device-width", initialScale: 1 };

/** The admin is its own root layout: English only, shares the shopper-chosen colour theme, no storefront header or footer. */
export default function AdminRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${adminDisplay.variable} ${adminBody.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="admin-root min-h-dvh font-sans antialiased">
        <Providers>
          <AdminShell>{children}</AdminShell>
        </Providers>
      </body>
    </html>
  );
}
