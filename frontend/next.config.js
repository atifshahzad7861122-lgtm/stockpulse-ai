/** @type {import('next').NextConfig} */
const nextConfig = {
  // Same-origin API proxy: the browser calls /api/* on this origin and
  // Next.js forwards to the FastAPI backend. This keeps the production build
  // working behind any public tunnel/host without a hardcoded backend URL.
  // Note: rewrites only apply when no page or route handler matches, so the
  // frontend's own /api/renders/* routes keep working.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
