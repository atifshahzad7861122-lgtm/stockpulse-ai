/** @type {import('next').NextConfig} */
const nextConfig = {
  // NOTE: no /api rewrites here. The browser client calls the backend
  // directly through NEXT_PUBLIC_API_URL (an absolute URL baked in at build
  // time), and the /api/renders/* routes are local Next.js route handlers
  // (they take precedence over rewrites anyway).
  //
  // A same-origin proxy to 127.0.0.1:8000 would break on Railway, where the
  // backend is a SEPARATE service — the frontend container has nothing
  // listening on 127.0.0.1:8000. Keep production free of localhost backends.
};

module.exports = nextConfig;
