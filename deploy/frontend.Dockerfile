# StockPulse AI — frontend (Next.js 14)
# Build context: repository root (~/workspace/stockpulse).
FROM node:20-slim AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# NEXT_PUBLIC_* is inlined into client JS at BUILD time, so it must be
# passed as a build arg (docker-compose / Render set it per environment).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
# Render queue spawns the Remotion CLI against remotion/index.tsx at runtime
# (frontend/lib/renders/queue.ts), so the compositions source must ship too.
COPY --from=builder /app/remotion ./remotion

EXPOSE 3000
# $PORT is injected by Render/Heroku-style hosts; defaults to 3000.
CMD ["sh", "-c", "npx next start -H 0.0.0.0 -p ${PORT:-3000}"]
