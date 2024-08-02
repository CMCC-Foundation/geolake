import re
from rdflib import Graph, Literal, Namespace, RDF, URIRef, BNode
from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF, XSD
import logging
from datetime import datetime

# Dictionary with accrualPeriodicity values for somw known datasets
ACCRUAL_PERIODICITY = {
    "blue-tongue": "AS_NEEDED",
    "iot-animal": "HOURLY",
    "pasture": "BIWEEKLY",
    "pi": "DAILY",
    "pi-long-term": "AS_NEEDED",
    "thi": "DAILY"
}

# Logging config
logging.basicConfig(level=logging.DEBUG)

# Namespaces for DCAT-AP, to be binded to the RDF graph
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCT = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
EDP = Namespace("https://europeandataportal.eu/voc#")
SPDX = Namespace("http://spdx.org/rdf/terms#")
ADMS = Namespace("http://www.w3.org/ns/adms#")
DQV = Namespace("http://www.w3.org/ns/dqv#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
SCHEMA = Namespace("http://schema.org/")
# Namespace for DCAT-AP IT
DCATAPIT = Namespace("http://dati.gov.it/onto/dcatapit#")


# Define classes for DCAT-AP entities (Dataset, Distribution and ContactPoint)

class ContactPoint:
    def __init__(self, name=None, email=None, webpage=None):
        self.name = name
        self.email = email
        self.webpage = webpage


class Distribution:
    def __init__(self, access_url=None, description=None, download_url=None,
                 media_type=None, format=None, rights=None, license=None, identifier=None):
        self.access_url = access_url
        self.description = description
        self.download_url = download_url
        self.media_type = media_type
        self.format = format
        self.rights = rights
        self.license = license
        self.identifier = identifier

    # Build the RDF graph for the distribution
    def to_graph(self, g):
        distribution = URIRef(self.uri)
        g.add((distribution, RDF.type, DCAT.Distribution))
        if self.access_url:
            g.add((distribution, DCAT.accessURL, URIRef(self.access_url)))
        if self.description:
            g.add((distribution, DCTERMS.description, Literal(self.description)))
        if self.download_url:
            g.add((distribution, DCAT.downloadURL, URIRef(self.download_url)))
        if self.media_type:
            g.add((distribution, DCTERMS.mediaType, URIRef(self.media_type)))
        if self.format:
            g.add((distribution, DCTERMS.format, URIRef(self.format)))
        if self.rights:
            rights_bnode = BNode()
            g.add((distribution, DCTERMS.rights, rights_bnode))
            g.add((rights_bnode, RDF.type, DCTERMS.RightsStatement))
            g.add((rights_bnode, DCTERMS.rights, URIRef(self.rights)))
        if self.license:
            license_bnode = BNode()
            g.add((distribution, DCTERMS.license, license_bnode))
            g.add((license_bnode, RDF.type, DCTERMS.LicenseDocument))
            g.add((license_bnode, DCTERMS.license, URIRef(self.license)))
        if self.identifier:
            g.add((distribution, DCTERMS.identifier, Literal(self.identifier)))
        return g


class DatasetDCAT:
    def __init__(self, uri, title=None, description=None, issued=None, identifier=None, contact_point=None):
        self.uri = uri
        self.title = title
        self.description = description
        self.issued = issued
        self.identifier = identifier
        self.contact_point = contact_point
        self.distributions = []

    def add_distribution(self, distribution):
        self.distributions.append(distribution)

    # Build the RDF graph for the dataset
    def to_graph(self, g):
        dataset = URIRef(self.uri)
        g.add((dataset, RDF.type, DCAT.Dataset))
        logging.debug(f"Adding to graph {g.identifier}: {dataset} a type {DCAT.Dataset}")

        if self.title:
            g.add((dataset, DCTERMS.title, Literal(self.title)))
        if self.description:
            g.add((dataset, DCTERMS.description, Literal(self.description)))
        if self.issued:
            g.add((dataset, DCTERMS.issued, Literal(self.issued, datatype=DCTERMS.W3CDTF)))
        if self.identifier:
            g.add((dataset, DCTERMS.identifier, Literal(self.identifier)))

        if self.contact_point:
            contact_bnode = BNode()
            g.add((dataset, DCAT.contactPoint, contact_bnode))
            g.add((contact_bnode, RDF.type, VCARD.Kind))
            if self.contact_point.name:
                g.add((contact_bnode, VCARD.fn, Literal(self.contact_point.name)))
            if self.contact_point.email:
                g.add((contact_bnode, VCARD.hasEmail, URIRef(f"mailto:{self.contact_point.email}")))
            if self.contact_point.webpage:
                g.add((contact_bnode, VCARD.hasURL, URIRef(self.contact_point.webpage)))

        for dist in self.distributions:
            distribution_bnode = BNode()
            g.add((dataset, DCAT.distribution, distribution_bnode))
            g.add((distribution_bnode, RDF.type, DCAT.Distribution))
            if dist.access_url:
                g.add((distribution_bnode, DCAT.accessURL, URIRef(dist.access_url)))
            if dist.description:
                g.add((distribution_bnode, DCTERMS.description, Literal(dist.description)))
            if dist.download_url:
                g.add((distribution_bnode, DCAT.downloadURL, URIRef(dist.download_url)))
            if dist.media_type:
                g.add((distribution_bnode, DCTERMS.mediaType, URIRef(dist.media_type)))
            if dist.format:
                g.add((distribution_bnode, DCTERMS.format, URIRef(dist.format)))
            if dist.rights:
                rights_bnode = BNode()
                g.add((distribution_bnode, DCTERMS.rights, rights_bnode))
                g.add((rights_bnode, RDF.type, DCTERMS.RightsStatement))
                g.add((rights_bnode, DCTERMS.rights, URIRef(dist.rights)))
            if dist.license:
                license_bnode = BNode()
                g.add((distribution_bnode, DCTERMS.license, license_bnode))
                g.add((license_bnode, RDF.type, DCTERMS.LicenseDocument))
                g.add((license_bnode, DCTERMS.license, URIRef(dist.license)))
            if dist.identifier:
                g.add((distribution_bnode, DCTERMS.identifier, Literal(dist.identifier)))

        return g


# Define classes for DCAT-AP IT entities (Catalog, Dataset, Distribution, and ContactPoint)

class ContactPointIT:
    def __init__(self, name=None, email=None, webpage=None):
        self.name = name
        self.email = email
        self.webpage = webpage

    def to_graph(self, g, parent):
        contact_bnode = BNode()
        g.add((parent, DCAT.contactPoint, contact_bnode))
        g.add((contact_bnode, RDF.type, VCARD.Kind))
        if self.name:
            g.add((contact_bnode, VCARD.fn, Literal(self.name)))
        if self.email:
            g.add((contact_bnode, VCARD.hasEmail, URIRef(f"mailto:{self.email}")))
        if self.webpage:
            g.add((contact_bnode, VCARD.hasURL, URIRef(self.webpage)))


class DistributionIT:
    def __init__(self, uri, access_url=None, description=None, download_url=None,
                 media_type=None, format=None, rights=None, license=None, identifier=None):
        self.uri = uri
        self.access_url = access_url
        self.description = description
        self.download_url = download_url
        self.media_type = media_type
        self.format = format
        self.rights = rights
        self.license = license
        self.identifier = identifier

    def to_graph(self, g):
        distribution = URIRef(self.uri)
        g.add((distribution, RDF.type, DCATAPIT.Distribution))
        if self.access_url:
            g.add((distribution, DCAT.accessURL, URIRef(self.access_url)))
        if self.description:
            g.add((distribution, DCTERMS.description, Literal(self.description)))
        if self.download_url:
            g.add((distribution, DCAT.downloadURL, URIRef(self.download_url)))
        if self.media_type:
            g.add((distribution, DCTERMS.mediaType, URIRef(self.media_type)))
        if self.format:
            g.add((distribution, DCTERMS.format, URIRef(self.format)))
        if self.rights:
            rights_bnode = BNode()
            g.add((distribution, DCTERMS.rights, rights_bnode))
            g.add((rights_bnode, RDF.type, DCTERMS.RightsStatement))
            g.add((rights_bnode, DCTERMS.rights, URIRef(self.rights)))
        if self.license:
            license_bnode = BNode()
            g.add((distribution, DCTERMS.license, license_bnode))
            g.add((license_bnode, RDF.type, DCTERMS.LicenseDocument))
            g.add((license_bnode, DCTERMS.license, URIRef(self.license)))
        if self.identifier:
            g.add((distribution, DCTERMS.identifier, Literal(self.identifier)))


class DatasetDCATAPIT:
    def __init__(self, uri, title=None, description=None, issued=None, identifier=None, contact_point=None):
        self.uri = uri
        self.title = title
        self.description = description
        self.issued = issued
        self.identifier = identifier
        self.contact_point = contact_point
        self.distributions = []

    def add_distribution(self, distribution):
        self.distributions.append(distribution)

    def to_graph(self, g):
        dataset = URIRef(self.uri)
        g.add((dataset, RDF.type, DCATAPIT.Dataset))
        if self.title:
            g.add((dataset, DCTERMS.title, Literal(self.title)))
        if self.description:
            g.add((dataset, DCTERMS.description, Literal(self.description)))
        if self.issued:
            g.add((dataset, DCTERMS.issued, Literal(self.issued, datatype=DCTERMS.W3CDTF)))
        if self.identifier:
            g.add((dataset, DCTERMS.identifier, Literal(self.identifier)))

        if self.contact_point:
            self.contact_point.to_graph(g, dataset)

        for dist in self.distributions:
            distribution_uri = URIRef(dist.uri)
            g.add((dataset, DCAT.distribution, distribution_uri))

        return g


class CatalogIT:
    def __init__(self, uri, title, description, modified, publisher_name, publisher_identifier, publisher_homepage,
                 publisher_email, dataset_uris=None):
        self.uri = uri
        self.title = title
        self.description = description
        self.modified = modified
        self.publisher_name = publisher_name
        self.publisher_identifier = publisher_identifier
        self.publisher_homepage = publisher_homepage
        self.publisher_email = publisher_email
        self.dataset_uris = dataset_uris if dataset_uris is not None else []

    def add_dataset(self, dataset_uri):
        self.dataset_uris.append(dataset_uri)

    def to_graph(self, g):
        catalog = URIRef(self.uri)
        g.add((catalog, RDF.type, DCATAPIT.Catalog))
        g.add((catalog, DCTERMS.title, Literal(self.title)))
        g.add((catalog, DCTERMS.description, Literal(self.description)))
        g.add((catalog, DCTERMS.modified, Literal(self.modified, datatype=DCTERMS.W3CDTF)))

        catalog_publisher_node = BNode()
        g.add((catalog, DCTERMS.publisher, catalog_publisher_node))
        g.add((catalog_publisher_node, RDF.type, FOAF.Agent))
        g.add((catalog_publisher_node, RDF.type, DCATAPIT.Agent))
        g.add((catalog_publisher_node, FOAF.name, Literal(self.publisher_name)))
        g.add((catalog_publisher_node, DCTERMS.identifier, Literal(self.publisher_identifier)))
        g.add((catalog_publisher_node, FOAF.homepage, URIRef(self.publisher_homepage)))
        g.add((catalog_publisher_node, FOAF.mbox, URIRef(f"mailto:{self.publisher_email}")))

        for dataset_uri in self.dataset_uris:
            g.add((catalog, DCAT.dataset, URIRef(dataset_uri)))

        return g

    # Function to convert to DCAT-AP IT format


def convert_to_dcat_ap_it(data, url):
    # Create separate graphs
    catalog_graph = Graph()
    datasets_graph = Graph()
    distributions_graph = Graph()
    vcard_graph = Graph()

    # Bind namespaces to all graphs
    for g in [catalog_graph, datasets_graph, distributions_graph, vcard_graph]:
        g.bind("dcatapit", DCATAPIT)
        g.bind("foaf", FOAF)
        g.bind("dcat", DCAT)
        g.bind("dct", DCT)
        g.bind("vcard", VCARD)
        g.bind("rdf", RDF)

    # Contact point URI
    contact_point_uri = URIRef("https://www.cmcc.it")

    # Create catalog
    catalog_uri = URIRef(url)
    catalog_graph.add((catalog_uri, RDF.type, DCATAPIT.Catalog))
    catalog_graph.add((catalog_uri, DCTERMS.title, Literal("Sebastien Catalog")))
    catalog_graph.add((catalog_uri, DCTERMS.description, Literal("A catalog of Sebastien datasets")))
    catalog_graph.add(
        (catalog_uri, DCTERMS.language, URIRef("http://publications.europa.eu/resource/authority/language/ITA")))
    catalog_graph.add((catalog_uri, DCTERMS.modified, Literal(datetime.now(), datatype=XSD.date)))

    # Add publisher information
    publisher = BNode()
    catalog_graph.add((catalog_uri, DCTERMS.publisher, publisher))
    catalog_graph.add((publisher, RDF.type, FOAF.Agent))
    catalog_graph.add((publisher, RDF.type, DCATAPIT.Agent))
    catalog_graph.add((publisher, FOAF.name, Literal("CMCC Foundation")))
    catalog_graph.add((publisher, DCTERMS.identifier, Literal("XW88C90Q")))
    catalog_graph.add((publisher, FOAF.homepage, URIRef("https://www.cmcc.it")))
    catalog_graph.add((publisher, FOAF.mbox, URIRef("mailto:dds-support@cmcc.it")))

    for dataset in data:
        if "dataset" not in dataset:
            dataset = {"dataset": dataset}
        dataset_id = dataset.get("dataset", {}).get("metadata", {}).get("id")
        dataset_uri = URIRef(f'{url}/{dataset_id}')

        # Add dataset reference to catalog
        catalog_graph.add((catalog_uri, DCAT.dataset, dataset_uri))

        # Create dataset
        datasets_graph.add((dataset_uri, RDF.type, DCATAPIT.Dataset))
        datasets_graph.add((dataset_uri, RDF.type, DCAT.Dataset))
        datasets_graph.add(
            (dataset_uri, DCTERMS.title, Literal(dataset.get("dataset", {}).get("metadata", {}).get("label"))))
        datasets_graph.add((dataset_uri, DCTERMS.description,
                            Literal(dataset.get("dataset", {}).get("metadata", {}).get("description"))))
        datasets_graph.add((dataset_uri, DCTERMS.issued, Literal(
            datetime.strptime(dataset.get("dataset", {}).get("metadata", {}).get("publication_date"), '%Y-%m-%d'),
            datatype=XSD.date)))
        datasets_graph.add((dataset_uri, DCTERMS.identifier, Literal(f"XW88C90Q:{dataset_id}")))
        # Add dct:modified, dcat:theme, dct:rightsHolder and dct:accrualPeriodicity
        datasets_graph.add((dataset_uri, DCTERMS.modified, Literal(datetime.now(), datatype=XSD.date)))
        datasets_graph.add(
            (dataset_uri, DCAT.theme, URIRef("http://publications.europa.eu/resource/authority/data-theme/AGRI")))
        datasets_graph.add((dataset_uri, DCTERMS.accrualPeriodicity, URIRef(
            f"http://publications.europa.eu/resource/authority/frequency/{ACCRUAL_PERIODICITY.get(dataset_id)}")))
        # Add publisher info on dataset
        publisher_dataset = BNode()
        datasets_graph.add((dataset_uri, DCTERMS.publisher, publisher_dataset))
        datasets_graph.add((publisher_dataset, RDF.type, FOAF.Agent))
        datasets_graph.add((publisher_dataset, RDF.type, DCATAPIT.Agent))
        datasets_graph.add((publisher_dataset, FOAF.name, Literal("CMCC Foundation")))
        datasets_graph.add((publisher_dataset, DCTERMS.identifier, Literal("XW88C90Q")))
        # Add rights holder BNode
        rights_holder_uri = BNode()
        datasets_graph.add((dataset_uri, DCTERMS.rightsHolder, rights_holder_uri))
        datasets_graph.add((rights_holder_uri, RDF.type, DCATAPIT.Agent))
        datasets_graph.add((rights_holder_uri, RDF.type, FOAF.Agent))
        datasets_graph.add((rights_holder_uri, DCTERMS.identifier, Literal("XW88C90Q")))
        datasets_graph.add((rights_holder_uri, FOAF.name, Literal("CMCC Foundation")))

        # Add contact point
        contact = dataset.get("dataset", {}).get("metadata", {}).get("contact")
        datasets_graph.add((dataset_uri, DCAT.contactPoint, contact_point_uri))

        # Create distribution
        # products = dataset.get("dataset", {}).get("metadata", {}).get("products", {}).get("monthly", {})
        distribution_uri = URIRef(f'{url}/{dataset_id}')
        datasets_graph.add((dataset_uri, DCAT.distribution, distribution_uri))
        distributions_graph.add((distribution_uri, RDF.type, DCAT.Distribution))
        distributions_graph.add((distribution_uri, DCAT.accessURL, distribution_uri))
        distributions_graph.add((distribution_uri, DCTERMS.description,
                                 Literal(dataset.get("dataset", {}).get("metadata", {}).get("description"))))
        license_uri = URIRef("https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40")
        license_document = BNode()
        distributions_graph.add((distribution_uri, DCTERMS.license, license_document))
        distributions_graph.add((license_document, RDF.type, DCATAPIT.LicenseDocument))
        distributions_graph.add(
            (license_document, DCTERMS.type, URIRef("http://purl.org/adms/licencetype/Attribution")))
        distributions_graph.add(
            (license_document, FOAF.name, Literal("Creative Commons Attribuzione 4.0 Internazionale (CC BY 4.0)")))
        distributions_graph.add((distribution_uri, DCTERMS.format,
                                 URIRef("http://publications.europa.eu/resource/authority/file-type/JSON")))
        distributions_graph.add((distribution_uri, RDF.type, DCATAPIT.Distribution))

    # Create vcard:Organization node
    contact = dataset.get("dataset", {}).get("metadata", {}).get("contact")
    vcard_graph.add((contact_point_uri, RDF.type, VCARD.Organization))
    vcard_graph.add((contact_point_uri, RDF.type, URIRef("http://dati.gov.it/onto/dcatapit#Organization")))
    vcard_graph.add((contact_point_uri, RDF.type, URIRef("http://xmlns.com/foaf/0.1/Organization")))
    vcard_graph.add((contact_point_uri, RDF.type, URIRef("http://www.w3.org/2006/vcard/ns#Kind")))
    vcard_graph.add((contact_point_uri, VCARD.fn, Literal(contact.get("name"))))
    vcard_graph.add((contact_point_uri, VCARD.hasEmail, URIRef(f"mailto:{contact.get('email')}")))
    vcard_graph.add((contact_point_uri, VCARD.hasURL, URIRef(contact.get("webpage"))))

    return catalog_graph, datasets_graph, distributions_graph, vcard_graph


def serialize_and_concatenate_graphs(catalog_graph, datasets_graph, distributions_graph, vcard_graph):
    # Serialize each graph to a string
    catalog_str = catalog_graph.serialize(format='pretty-xml')
    datasets_str = datasets_graph.serialize(format='pretty-xml')
    distributions_str = distributions_graph.serialize(format='pretty-xml')
    vcard_str = vcard_graph.serialize(format='pretty-xml')

    # Remove XML headers and opening <rdf:RDF> tags from datasets and distributions and vcard strings
    datasets_str = re.sub(r'<\?xml[^>]+\?>', '', datasets_str)
    datasets_str = re.sub(r'<rdf:RDF[^>]*>', '', datasets_str, count=1).rsplit('</rdf:RDF>', 1)[0]
    distributions_str = re.sub(r'<\?xml[^>]+\?>', '', distributions_str)
    distributions_str = re.sub(r'<rdf:RDF[^>]*>', '', distributions_str, count=1).rsplit('</rdf:RDF>', 1)[0]
    vcard_str = re.sub(r'<\?xml[^>]+\?>', '', vcard_str)
    vcard_str = re.sub(r'<rdf:RDF[^>]*>', '', vcard_str, count=1).rsplit('</rdf:RDF>', 1)[0]

    # Concatenate the strings
    final_str = catalog_str.rsplit('</rdf:RDF>', 1)[0] + datasets_str + distributions_str + vcard_str + '</rdf:RDF>'

    # Manually add the vcard namespace declaration
    final_str = final_str.replace(
        '<rdf:RDF',
        '<rdf:RDF xmlns:vcard="http://www.w3.org/2006/vcard/ns#"'
    )

    return final_str


def convert_to_dcat_ap(data, url):
    logging.debug("Starting convert_to_dcat_ap function")

    g = Graph()

    # Bind namespaces
    g.bind("dcat", DCAT)
    g.bind("DCT", DCT)
    g.bind("foaf", FOAF)
    g.bind("vcard", VCARD)
    g.bind("edp", EDP)
    g.bind("spdx", SPDX)
    g.bind("adms", ADMS)
    g.bind("dqv", DQV)
    g.bind("skos", SKOS)
    g.bind("schema", SCHEMA)

    # Placeholder URI
    dataset_uri = url

    if not isinstance(data, list):
        data = [data]

    for dataset in data:
        # Check if "dataset" key is present, if it isnt, wrap the dict in it
        if "dataset" not in dataset:
            dataset = {"dataset": dataset}

        # Add the URL to the data
        dataset["url"] = url

        # Create dataset and convert the field names to DCAT-AP
        metadata = DatasetDCAT(
            uri=f'{dataset_uri}/{dataset.get("dataset", {}).get("metadata", {}).get("id")}',
            title=dataset.get("dataset", {}).get("metadata", {}).get("label"),
            description=dataset.get("dataset", {}).get("metadata", {}).get("description"),
            issued=dataset.get("dataset", {}).get("metadata", {}).get("publication_date"),
            identifier=dataset.get("dataset", {}).get("metadata", {}).get("id"),
        )

        # Create contact point and convert the field names to DCAT-AP
        contact = dataset.get("dataset", {}).get("metadata", {}).get("contact")
        contact_point = ContactPoint(
            name=contact.get("name"),
            email=contact.get("email"),
            webpage=contact.get("webpage"),
        )
        metadata.contact_point = contact_point

        # Create distributions and convert the field names to DCAT-AP
        products = dataset.get("dataset", {}).get("products", {}).get("monthly", {})
        distribution = Distribution(
            access_url=url,
            description=products.get("description"),
        )
        metadata.add_distribution(distribution)

        # Add dataset to graph
        metadata.to_graph(g)

    return g