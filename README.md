[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.10598417.svg)](https://doi.org/10.5281/zenodo.10598417)

# geolake

## Description

**geolake** is an open source framework for management, storage, and analytics of Earth Science data. geolake implements the concept of a data lake as a central location that holds a large amount of data in its native and raw format. 

**geolake** do not impose any schema when ingesting the data, however it provides a unified Data Model and API for geoscientific datasets. The data is kept in the original format and storage, and the in-memory data structure is built on-the-fly for the processing analysis.

The system has been designed using a cloud-native architecture, based on containerized microservices, that facilitates the development, deployment and maintenance of the system itself. It has been implemented by integrating different open source frameworks, tools and libraries and can be easily deployed using the Kubernetes platform and related tools such as kubectl.

It uses [geokube](https://github.com/CMCC-Foundation/geokube) as an Analytics Engine to perform geospatial operations.

## Authors

**Project Lead**:
[Marco Mancini](https://github.com/km4rcus)

**Main Developers**
- [Jakub Walczak](https://github.com/jamesWalczak)
- [Mirko Stojiljkovic](https://github.com/MMStojiljkovic)
- [Valentina Scardigno](https://github.com/vale95-eng)

