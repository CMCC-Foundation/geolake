from oaipmh.server import ServerBase, oai_dc_writer
from oaipmh.metadata import MetadataRegistry, oai_dc_reader
import metadata_provider
from lxml.etree import fromstring, tostring
import logging

# Function to write metadata in dcat_ap format (RDF/XML), otherwise it would use the default format (oai_dc) 
def dcat_ap_writer(metadata_element, metadata):
    rdf_string = metadata["rdf"]
    rdf_element = fromstring(bytes(rdf_string, encoding='utf-8'))
    
    for child in rdf_element:
        metadata_element.append(child)
        logging.debug(f"Metadata Element: {tostring(metadata_element, pretty_print=True).decode('utf-8')}")


# Create reader for dcat_ap metadata
def dcat_ap_reader(element):
    rdf_string = tostring(element, encoding='unicode')
    return {"rdf": rdf_string}

# Server class, it defines writers and readers, as well as the metadata provider (metadata_provider.py)
class MyServer(ServerBase):
    def __init__(self):
        metadata_registry = MetadataRegistry()
        metadata_registry.registerWriter("oai_dc", oai_dc_writer)
        metadata_registry.registerReader("oai_dc", oai_dc_reader)
        metadata_registry.registerWriter("dcat_ap", dcat_ap_writer)
        metadata_registry.registerReader("dcat_ap", dcat_ap_reader)
        server = metadata_provider.MyMetadataProvider()
        super(MyServer, self).__init__(server, metadata_registry)


oai_server = MyServer()
