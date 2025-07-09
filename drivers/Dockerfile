ARG REGISTRY=rg.fr-par.scw.cloud/geokube
#ARG TAG=2025.03.25.10.56
ARG TAG=2025.07.09.08.36
FROM $REGISTRY/geokube:$TAG

ADD . /opt/intake_geokube
RUN pip install /opt/intake_geokube --break-system-packages
RUN rm -rf /opt/intake_geokube
