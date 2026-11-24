ARG REGISTRY=gtramonte
# Version of the base geokube image (decoupled from the geolake release TAG).
ARG GEOKUBE_TAG=2026.06.2.1
FROM $REGISTRY/geokube:$GEOKUBE_TAG

ADD . /opt/intake_geokube
RUN pip install /opt/intake_geokube --break-system-packages
RUN rm -rf /opt/intake_geokube
