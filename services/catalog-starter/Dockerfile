# TODO шаг 15: образ сервиса.
# Сейчас всё в одну стадию и от root: в образ уедут gcc, кэш pip и лишние права.
# Контекст сборки это корень репозитория.
FROM python:3.14-slim
WORKDIR /app
COPY services/catalog-starter .
RUN apt-get update && apt-get install -y --no-install-recommends gcc && pip install .
EXPOSE 8182
ENTRYPOINT ["uvicorn", "catalog_starter.main:app", "--host", "0.0.0.0", "--port", "8182"]
