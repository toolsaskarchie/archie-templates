FROM python:3.11-slim
RUN pip install --no-cache-dir boto3
COPY agent.py /app/agent.py
WORKDIR /app
EXPOSE 8080
CMD ["python", "agent.py"]
