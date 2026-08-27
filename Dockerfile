# syntax=docker/dockerfile:1.6
# ====================================================================
# Automatic Video Dubbing Engine — frontend image (production)
# Multi-stage build using Next.js standalone output.
# ====================================================================

# --- Stage 1: install deps ---
FROM node:20-alpine AS deps
WORKDIR /app
RUN apk add --no-cache libc6-compat
COPY package.json bun.lock* package-lock.json* ./
RUN npm install --no-audit --no-fund

# --- Stage 2: build ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Build uses BACKEND_URL for the /api/* rewrite. In docker-compose the
# frontend container reaches the backend via its service name "backend".
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL
RUN npm run build

# --- Stage 3: runtime (minimal) ---
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# Copy the standalone server, static assets, and public files.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
