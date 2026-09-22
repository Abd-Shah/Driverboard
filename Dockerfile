FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY tools ./tools
RUN pip install --no-cache-dir .
CMD ["uvicorn", "driver_leaderboard.main:app", "--host", "0.0.0.0", "--port", "8000"]

