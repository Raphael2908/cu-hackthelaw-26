# Supervision Cockpit — frontend (Next.js App Router). Dev server for the demo.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

# Bind to all interfaces so the host can reach the container.
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
