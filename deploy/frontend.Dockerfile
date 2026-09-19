# StockPulse AI — frontend (Next.js 14)
# Build context: repository root (~/workspace/stockpulse).
FROM node:20-slim AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# NEXT_PUBLIC_* is inlined into client JS at BUILD time. Hosts like Railway
# cannot receive custom Docker build args, so we bake a PLACEHOLDER here and
# the container replaces it with the runtime NEXT_PUBLIC_API_URL on startup
# (see deploy/docker/inject-api-url.js). Local docker builds can still pass a
# real URL: --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000/api
ARG NEXT_PUBLIC_API_URL=__STOCKPULSE_API_URL__
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
# Render queue spawns the Remotion CLI against remotion/index.tsx at runtime
# (frontend/lib/renders/queue.ts), so the compositions source must ship too.
COPY --from=builder /app/remotion ./remotion
# Runtime API-URL injection (see the builder-stage comment above).
COPY deploy/docker/inject-api-url.js ./inject-api-url.js

EXPOSE 3000
# $PORT is injected by Render/Heroku-style hosts; defaults to 3000.
# On startup the placeholder API URL baked into the client bundle is replaced
# with the runtime NEXT_PUBLIC_API_URL before the server starts.
CMD ["sh", "-c", "node ./inject-api-url.js && npx next start -H 0.0.0.0 -p ${PORT:-3000}"]
