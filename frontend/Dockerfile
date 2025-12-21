FROM node:lts-alpine AS builder

WORKDIR /app

# Accept build argument for API URL
# Default to backend service name for direct cluster connection
ARG NEXT_PUBLIC_API_URL=http://backend-fastapi-service.crypto-app.svc.cluster.local:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json ./
RUN npm install

COPY . .
RUN npm run build

FROM node:lts-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app ./

EXPOSE 3000

CMD ["npm", "start"]


