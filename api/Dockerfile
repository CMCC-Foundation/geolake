ARG REGISTRY=rg.fr-par.scw.cloud/geolake
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

RUN apt update && apt install -y cron

WORKDIR /app
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY app /app
EXPOSE 80

COPY ./healtcheck.* /opt/

RUN chmod +x /opt/healtcheck.sh
RUN crontab -u root /opt/healtcheck.cron
RUN service cron start

#CMD ["uvicorn", "app.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]

ENTRYPOINT service cron start && uvicorn app.main:app --proxy-headers --host 0.0.0.0 --port 80