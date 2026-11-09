# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS deps

WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements.txt -t /deps

FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/deps

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin app

COPY --from=deps /deps /deps
COPY --chown=1000:1000 app /app/app
COPY --chown=1000:1000 alembic /app/alembic
COPY --chown=1000:1000 alembic.ini /app/alembic.ini
COPY --chown=1000:1000 scripts /app/scripts

USER 1000:1000

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM deps AS test-deps
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements-dev.txt -t /test-deps

FROM runtime AS test
COPY --from=test-deps /test-deps /deps
COPY --chown=1000:1000 tests /app/tests
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
