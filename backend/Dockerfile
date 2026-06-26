FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system -e .

COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
