# front/Dockerfile
# Étape 1 : Build
FROM node:20-alpine AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


# Étape 2 : Production avec Nginx
FROM nginx:alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# On écrit la configuration avec les DEUX accolades fermantes à la fin
RUN echo 'server {' > /etc/nginx/conf.d/default.conf && \
    echo '    listen 8080;' >> /etc/nginx/conf.d/default.conf && \
    echo '    location / {' >> /etc/nginx/conf.d/default.conf && \
    echo '        root /usr/share/nginx/html;' >> /etc/nginx/conf.d/default.conf && \
    echo '        index index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '        try_files $uri $uri/ /index.html;' >> /etc/nginx/conf.d/default.conf && \
    echo '    }' >> /etc/nginx/conf.d/default.conf && \
    echo '}' >> /etc/nginx/conf.d/default.conf

ENV PORT=8080
EXPOSE $PORT

# Au démarrage, on remplace dynamiquement "8080" par la valeur de $PORT, puis on lance Nginx
CMD ["sh", "-c", "sed -i \"s/listen 8080;/listen ${PORT};/g\" /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]