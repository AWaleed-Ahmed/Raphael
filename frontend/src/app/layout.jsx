import "../features/Pages/Landing/landing.css";
import "./tailwind.css";

export const metadata = {
  title: "Raphael — Clarity after a failed deploy",
  description:
    "Raphael investigates Kubernetes deployment failures, tests narrow repairs in an isolated sandbox, and prepares draft pull requests for human review.",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "Raphael — Clarity after a failed deploy",
    description:
      "Deployment repair with evidence, isolated validation, and human control.",
    type: "website",
  },
};

export const viewport = { themeColor: "#11121a" };

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link
          rel="preload"
          href="/fonts/fontshare-switzer-400.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <link
          rel="preload"
          href="/fonts/fontshare-sentient-400.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <link
          rel="preload"
          href="/fonts/fontshare-telma-500.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
