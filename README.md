<div align="center">
<img src="docs/img/logo.svg" width="40%" height="40%">
</div>


## 📖 Description

**geolake** is an open source framework for management, storage, and analytics of Earth Science data. geolake implements the concept of a data lake as a central location that holds a large amount of data in its native and raw format. 

**geolake** do not impose any schema when ingesting the data, however it provides a unified Data Model and API for geoscientific datasets. The data is kept in the original format and storage, and the in-memory data structure is built on-the-fly for the processing analysis.

The system has been designed using a cloud-native architecture, based on containerized microservices, that facilitates the development, deployment and maintenance of the system itself. It has been implemented by integrating different open source frameworks, tools and libraries and can be easily deployed using the Kubernetes platform and related tools such as kubectl.

It uses [geokube](https://github.com/CMCC-Foundation/geokube) as an Analytics Engine to perform geospatial operations.


## 🖋️ Authors
**Project Lead**:
1. [Marco Mancini](https://github.com/km4rcus) <a href="https://orcid.org/0000-0002-5632-9484"><img alt="ORCID logo" src="https://info.orcid.org/wp-content/uploads/2019/11/orcid_16x16.png" width="16" height="16" /></a>
**Main Developers**
1. [Jakub Walczak](https://github.com/jamesWalczak) <a href="https://orcid.org/0000-0002-5632-9484"><img alt="ORCID logo" src="https://info.orcid.org/wp-content/uploads/2019/11/orcid_16x16.png" width="16" height="16" /></a>
1.[Mirko Stojiljkovic](https://github.com/MMStojiljkovic) <a href="https://orcid.org/0000-0003-2256-1645"><img alt="ORCID logo" src="https://info.orcid.org/wp-content/uploads/2019/11/orcid_16x16.png" width="16" height="16" /></a>
1. [Valentina Scardigno](https://github.com/vale95-eng) <a href="https://orcid.org/0000-0002-0123-5368"><img alt="ORCID logo" src="https://info.orcid.org/wp-content/uploads/2019/11/orcid_16x16.png" width="16" height="16" /></a>


## 📜 Cite Us
```bibtex
@SOFTWARE{geolake,
  author = {Mancini, Marco and
            Walczak, Jakub and
            Stojiljković, Mirko and
            Scardigno, Valentina},
  title = {geolake},
  month = jan,
  year = 2024,
  note = {{Available in GitHub: https://github.com/CMCC-Foundation/geolake}},
}
```

## 🙏 Acknowledgement
This work was funded by ...

## 🎬 References
See [References](https://opengeolake.github.io/) page for details
