from rdflib import Graph, Literal, Namespace, RDF, URIRef, BNode
from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF
import logging

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
            g.add((dataset, DCT.title, Literal(self.title)))
        if self.description:
            g.add((dataset, DCT.description, Literal(self.description)))
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
    
# Function to convert to DCAT-AP IT format
def convert_to_dcat_ap_it(graph, catalog_uri):
    g = graph

    # Bind DCATAPIT namespace to graph
    g.bind("dcatapit", DCATAPIT)

    # Create catalog and add it to the graph
    catalog = URIRef(catalog_uri)
    g.add((catalog, RDF.type, DCATAPIT.Catalog))
    g.add((catalog, DCTERMS.title, Literal("Sebastien Catalog")))
    g.add((catalog, DCTERMS.description, Literal("A catalog of Sebastien datasets")))
    g.add((catalog, DCTERMS.publisher, URIRef("https://www.cmcc.it/")))
    g.add((catalog, DCTERMS.modified, Literal("2023-07-09", datatype=DCTERMS.W3CDTF)))

    # Find all datasets in graph
    for dataset_uri in g.subjects(RDF.type, DCAT.Dataset):
        # Create dcatapit:Dataset node
        dcatapit_dataset_node = BNode()
        g.add((dcatapit_dataset_node, RDF.type, DCATAPIT.Dataset))

        # Wrap existing dataset elements under dcatapit:Dataset
        for s, p, o in g.triples((dataset_uri, None, None)):
            g.remove((dataset_uri, p, o))
            g.add((dcatapit_dataset_node, p, o))

        # Add dcat:dataset relation to the new dcatapit:Dataset node
        g.add((dataset_uri, DCAT.dataset, dcatapit_dataset_node))

        # Add dcatapit:Dataset to catalog
        g.add((catalog, DCATAPIT.dataset, dataset_uri))

        # Add mandatory fields with placeholder values
        g.add((dcatapit_dataset_node, DCAT.theme, URIRef("http://publications.europa.eu/resource/authority/data-theme/AGRI")))
        g.add((dcatapit_dataset_node, DCTERMS.rightsHolder, URIRef("https://www.cmcc.it/")))
        g.add((dcatapit_dataset_node, DCTERMS.accrualPeriodicity, URIRef("http://publications.europa.eu/resource/authority/frequency/WEEKLY")))

        # Change Distribution namespace to DCATAPIT
        for s, p, o in g.triples((dcatapit_dataset_node, DCAT.distribution, None)):
            g.remove((s, p, o))
            g.add((s, DCATAPIT.distribution, o))
            g.add((o, RDF.type, DCATAPIT.Distribution))

    return g



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