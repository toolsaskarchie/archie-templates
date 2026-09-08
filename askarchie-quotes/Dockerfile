# THIS BRANCH IS THE CONTAINER. On `main` this file lives in `container/`,
# because there the page renders a random line, holds nothing, and a Lambda
# handler is the honest shape of it. Here it does not: the page counts what it
# has served and keeps what visitors have written, and state in a process that
# is recreated per request is state that does not survive being read.
#
# A Dockerfile AT THE APP ROOT is a declaration that the app IS a container.
# Archie's container delivery reads DOCKERFILE_PATH=Dockerfile from the app
# root and does not generate one, so a repository without this file here
# cannot be delivered as a container at all.
#
# `handler.py` is still the whole page and is untouched — this image runs
# `server.py`, which imports the page and the quotes from it, so one
# repository serves both shapes and neither can drift from the other.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app
COPY handler.py ./
COPY container/server.py ./

# Nothing to install — requirements.txt is empty on purpose, and keeping it that
# way is what makes this image build in seconds with no network at build time.

# Not root. A demo is still somebody's account.
RUN useradd --create-home --uid 10001 app
USER app

# WHAT IS IN HERE DOES NOT SURVIVE THIS CONTAINER. The counter and the
# submissions live in the process (see the note at the top of handler.py), so
# every restart, scale-out and redeploy starts them again from zero. Somewhere
# durable has to hold them; this image cannot, and says so rather than looking
# like it can.
EXPOSE 8080
CMD ["python", "server.py"]
