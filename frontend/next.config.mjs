import { fileURLToPath } from "node:url";

export default {
  trailingSlash: true,
  reactStrictMode: true,
  turbopack: { root: fileURLToPath(new URL(".", import.meta.url)) },
  async rewrites() {
    return [
      // Opt-in loopback proxy for the local console; never expose backend secrets.
      ...(process.env.NODE_ENV === "development" && process.env.RAPHAEL_DEV_API_PROXY === "true"
        ? [{ source: "/api/:path*/", destination: "http://127.0.0.1:8091/:path*" }]
        : []),
      { source: "/console/", destination: "/legacy/console/index.html" },
      { source: "/console/:path+/", destination: "/legacy/console/index.html" },
      { source: "/direction/", destination: "/legacy/direction/index.html" },
      { source: "/assets/:path*", destination: "/legacy/assets/:path*" },
    ];
  },
};
