# frontend/Dockerfile
# ─────────── Étape 1 : Build Vite ───────────
FROM node:20-alpine AS build-stage
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Variables Vite injectées à la compilation
# Doivent être passées au docker build via --build-arg
ARG VITE_API_URL
ARG VITE_CONTRACT_ADDRESS
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_CONTRACT_ADDRESS=$VITE_CONTRACT_ADDRESS

RUN npm run build

# ─────────── Étape 2 : Production avec Nginx ───────────
FROM nginx:alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Conf nginx en une fois (cat heredoc, plus lisible que les echo en cascade)
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 8080;
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
EOF

ENV PORT=8080
EXPOSE $PORT

# Remplace 8080 par la valeur de $PORT au démarrage (utile pour Scaleway Serverless Containers)
CMD ["sh", "-c", "sed -i \"s/listen 8080;/listen ${PORT};/g\" /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
