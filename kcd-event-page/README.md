# kcd-event-page

A one-page site for a cloud native community event (KCD). The container is nginx; at
startup it renders the page from four environment variables:

| Variable | Example |
|---|---|
| `EVENT_NAME` | KCD Argentina |
| `CITY` | Buenos Aires |
| `MESSAGE` | ¡Gracias Argentina! 🇦🇷❤️ |
| `NEXT_EVENT` | Nos vemos pronto 🤘 |

Values are HTML-escaped. The container listens on port 80 and answers `/healthz`
with `200 ok` for load balancer health checks.

```bash
docker build -t kcd-event-page .
docker run --rm -p 8080:80 -e EVENT_NAME="KCD Sevilla" -e CITY="Sevilla" kcd-event-page
```
