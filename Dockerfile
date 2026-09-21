FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false \
    PIP_NO_CACHE_DIR=1
COPY requirements.lock pyproject.toml ./
COPY src ./src
RUN pip install -r requirements.lock && pip install --no-deps .
COPY config ./config
COPY dbt ./dbt
COPY tests ./tests
COPY scripts ./scripts
COPY powerbi ./powerbi
ENTRYPOINT ["rail"]
CMD ["demo"]
