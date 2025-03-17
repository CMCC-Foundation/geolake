ARG REGISTRY=rg.fr-par.scw.cloud/geokube
#ARG TAG=v0.2.6b2
#ARG TAG=2024.05.03.10.36
ARG TAG=v0.2.7.9
FROM $REGISTRY/geokube:$TAG

ADD . /opt/intake_geokube
RUN pip install /opt/intake_geokube --break-system-packages
RUN rm -rf /opt/intake_geokube
