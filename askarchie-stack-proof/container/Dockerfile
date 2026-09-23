# Build from the package root:  docker build -f container/Dockerfile -t askarchie-stack-proof .
# One image for ECS (ARCHIE_STACK=alb+ecs+rds) and EKS (ARCHIE_STACK=eks+configmap).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app

# pg8000 is pure Python (RDS). boto3 only matters if a container stack includes sqs/dynamodb.
RUN pip install --no-cache-dir pg8000==1.31.2 boto3

# RDS CA bundle so the TLS hop is verified, not just encrypted.
ADD https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /app/rds-ca.pem

COPY common/app.py common/archie_proof.py common/backends.py common/quotes.json ./
COPY container/server.py ./

RUN useradd --uid 10001 --no-create-home app && chmod 644 /app/rds-ca.pem
USER app
EXPOSE 8080
CMD ["python", "server.py"]
