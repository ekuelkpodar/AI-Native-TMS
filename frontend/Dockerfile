# UNVERIFIED — docker was not installed on the build VM, so this image has
# never been built or run. Provided to complete the docker-compose layout.
FROM node:24-alpine AS build

WORKDIR /srv/web

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# In compose, /api is proxied to the api service by nginx (see nginx.conf).
ARG VITE_API_URL=/api/v1
RUN npm run build

FROM nginx:alpine

COPY --from=build /srv/web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
