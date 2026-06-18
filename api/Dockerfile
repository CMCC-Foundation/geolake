ARG REGISTRY=gtramonte
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

RUN apt update && apt install -y cron curl

WORKDIR /app
# Dependencies are declared in pyproject.toml (single manifest for prod + dev).
# Built/installed from /code, which preserves the repo layout
# (pyproject.toml + app/) so setuptools' `package-dir = {"" = "app"}` resolves.
# The runtime keeps importing from the flat /app layout copied below.
COPY pyproject.toml /code/pyproject.toml
COPY app /code/app
RUN pip install --no-cache-dir /code --break-system-packages
COPY app /app
EXPOSE 80

COPY ./healtcheck.* /opt/

RUN chmod +x /opt/healtcheck.sh
RUN crontab -u root /opt/healtcheck.cron

CMD ["uvicorn", "app.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]

