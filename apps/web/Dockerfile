FROM node:22-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json turbo.json pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/
# using corepack for pnpm
RUN corepack enable pnpm
RUN pnpm install --frozen-lockfile=false

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY . .

# Run turborepo build for web
RUN corepack enable pnpm
RUN pnpm run build --filter=web...

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
# ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/apps/web/public ./apps/web/public

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# Note: this CMD assumes output: 'standalone' in next.config.js which we didn't add,
# For standard start:
CMD ["npm", "run", "start", "--prefix", "apps/web"]

# --- DEVELOPMENT TARGET ---
FROM base AS development
WORKDIR /app
RUN corepack enable pnpm
CMD ["pnpm", "--filter", "web", "dev"]
