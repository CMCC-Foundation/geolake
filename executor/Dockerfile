ARG REGISTRY=rg.fr-par.scw.cloud/geolake
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

WORKDIR /app
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt --break-system-packages
COPY app /app

CMD [ "python", "main.py" ]
