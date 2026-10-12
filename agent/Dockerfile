FROM node:22-bookworm-slim
WORKDIR /app/agent
COPY agent/package*.json ./
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm ci --ignore-scripts --no-audit --no-fund --registry=$NPM_REGISTRY
COPY agent/*.mjs ./
ENV AGENT_HOST=0.0.0.0
EXPOSE 8787
CMD ["node", "server.mjs"]

