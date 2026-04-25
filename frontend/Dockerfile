# Étape 1 : Construction (Build)
FROM node:20-alpine as build-stage

WORKDIR /app

# Copier les fichiers de configuration
COPY package*.json ./

# Installer les dépendances
RUN npm install

# Copier le reste du code
COPY . .

# Compiler l'application pour la production
RUN npm run build

# Étape 2 : Serveur de Production (Nginx)
FROM nginx:stable-alpine as production-stage

# Copier les fichiers compilés depuis l'étape de build
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copier une configuration Nginx personnalisée
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
