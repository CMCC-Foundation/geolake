ARG REGISTRY=gtramonte
# Versione dell'immagine base geokube (disaccoppiata dal TAG di release geolake).
ARG GEOKUBE_TAG=2026.03.1
FROM $REGISTRY/geokube:$GEOKUBE_TAG

ADD . /opt/intake_geokube
RUN pip install /opt/intake_geokube --break-system-packages
RUN rm -rf /opt/intake_geokube
