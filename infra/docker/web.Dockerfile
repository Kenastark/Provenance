# syntax=docker/dockerfile:1
FROM node:20-slim

WORKDIR /app

RUN corepack enable

COPY apps/web/package.json apps/web/pnpm-lock.yaml* ./
RUN pnpm install --no-frozen-lockfile

COPY apps/web ./

EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
