FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm ci && npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.d/40-certs.sh /docker-entrypoint.d/40-certs.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/40-certs.sh && chmod +x /docker-entrypoint.d/40-certs.sh
COPY --from=build /src/dist /usr/share/nginx/html
