ARG REGISTRY=rg.fr-par.scw.cloud/geolake
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

RUN apt update && apt install -y cron curl


WORKDIR /app
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt --break-system-packages
COPY app /app

COPY ./healtcheck.* /opt/

RUN chmod +x /opt/healtcheck.sh
RUN crontab -u root /opt/healtcheck.cron

CMD [ "python", "main.py" ]
