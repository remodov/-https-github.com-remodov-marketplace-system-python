FROM python:3.14-slim AS build
WORKDIR /app
RUN python -m venv /opt/venv
COPY services/catalog-starter/pyproject.toml ./
RUN /opt/venv/bin/pip install --no-cache-dir --only-deps .

FROM python:3.14-slim
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 65532 app && useradd --uid 65532 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY services/catalog-starter/alembic.ini ./
COPY services/catalog-starter/catalog_starter ./catalog_starter
COPY services/catalog-starter/migrations ./migrations
USER app
EXPOSE 8182
ENTRYPOINT ["uvicorn", "catalog_starter.main:app", "--host", "0.0.0.0", "--port", "8182"]
