# Archie's container delivery builds from a Dockerfile at the app root — the
# kaniko job reads DOCKERFILE_PATH=Dockerfile and does not generate one, so a
# repo without this file cannot be delivered as a container at all.
#
# `handler.py` stays the Lambda entrypoint and is untouched. This image runs
# `server.py`, which imports the page and the quotes from it, so one repository
# serves both deliveries and neither can drift from the other.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Built from the APP root, not from here:  docker build -f container/Dockerfile .
# The Dockerfile lives in a subdirectory on purpose — a Dockerfile at the app
# root is a declaration that the app IS a container, and this one is a second
# way to run something that is a Lambda handler first.
WORKDIR /app
COPY handler.py ./
COPY container/server.py ./

# Nothing to install — requirements.txt is empty on purpose, and keeping it that
# way is what makes this image build in seconds with no network at build time.

# Not root. A demo is still somebody's account.
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080
CMD ["python", "server.py"]
