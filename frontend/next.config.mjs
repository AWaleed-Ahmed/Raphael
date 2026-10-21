import { fileURLToPath } from "node:url";

export default {
  trailingSlash: true,
  reactStrictMode: true,
  turbopack: { root: fileURLToPath(new URL(".", import.meta.url)) },
  async rewrites() {
    return [
      { source: "/console/", destination: "/legacy/console/index.html" },
      { source: "/console/:path+/", destination: "/legacy/console/index.html" },
      { source: "/direction/", destination: "/legacy/direction/index.html" },
      { source: "/assets/:path*", destination: "/legacy/assets/:path*" },
    ];
  },
};
