# AskArchie Quotes

A one-page site that shows a different AskArchie quote on every request. No
dependencies, no database, no build step — it exists to be **deployed**, which
is the only thing it is for.

It is the demo application in the AskArchie videos: something real to put on
real infrastructure, small enough that nothing about the app distracts from
what the platform is doing.

```
askarchie-quotes/
├── handler.py            the app: a Lambda handler that renders the page
├── requirements.txt      empty, deliberately
└── container/            a second way to run the same app
    ├── Dockerfile
    └── server.py         the same page over HTTP
```

## Why the Dockerfile is not at the root

**A Dockerfile at an app's root is a declaration that the app IS a container**,
and Archie reads it that way — ahead of any inference about the source, because
the author writing one down beats anything guessed from the code.

This app is a Lambda handler first. Putting the Dockerfile at the root made it
read as a container, and a request to host a one-page site narrowed to ECS and
Kubernetes: a VPC, a load balancer and a container build, for a page nobody has
visited yet.

So the root stays `handler.py` + `requirements.txt` — which is what the app
actually is — and the container variant lives one directory down, where it is
available without claiming to be the answer.

**Do not move it back up.** If you want Archie to treat this as a container,
that is the change, and it should be a decision rather than a tidy-up.

## Running it

Locally, over HTTP:

```bash
python3 container/server.py          # http://localhost:8080
```

As a container — built from the **app root**, not from `container/`:

```bash
docker build -f container/Dockerfile -t quotes .
docker run -p 8080:8080 quotes
```

`/health`, `/healthz` and `/ping` answer `200 ok`. A load balancer health-checks
a path and drains a target that fails it, so a container serving only `/` comes
up, never passes, and the URL 502s with every resource present and looking
healthy in the console.

As a Lambda: `handler.handler`, `python3.12`, no layer needed.

## How Archie delivers it

The app declares nothing and needs no configuration. Archie reads the repository
and decides which runtimes can receive it:

| What it finds | Format | Runtimes that can take it |
|---|---|---|
| `def handler(event, context)` at the top level | `lambda_zip` | Lambda |
| a `Dockerfile` at the app root | `container` | ECS, Kubernetes, Container Apps |

Today it is the first row. A public Lambda function URL serves the page over
HTTPS with no VPC and no load balancer, and a custom domain is added later by
putting CloudFront in front — the function and its code are untouched, which is
the point.

`requirements.txt` is empty on purpose. Nothing is fetched at build time, the
image builds in seconds, and there is no supply chain to think about in a demo.

## One page, two ways to serve it

`container/server.py` imports `QUOTES` and `_page` from `handler.py` rather than
carrying its own copy. There is one definition of what the site says, so the
Lambda and the container cannot drift into showing different pages — which they
would, the first time somebody edited one of them.
