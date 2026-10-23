FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html.template /usr/share/nginx/index.html.template
# Scripts in /docker-entrypoint.d run before nginx starts.
COPY render-page.sh /docker-entrypoint.d/40-render-page.sh
RUN chmod 0755 /docker-entrypoint.d/40-render-page.sh

ENV EVENT_NAME="KCD Argentina" \
    CITY="Buenos Aires" \
    MESSAGE="¡Gracias Argentina! 🇦🇷❤️" \
    NEXT_EVENT="Nos vemos pronto 🤘"

EXPOSE 80
HEALTHCHECK CMD wget -qO- http://127.0.0.1/healthz || exit 1
