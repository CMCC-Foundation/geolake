from oaipmh.common import Identify, Metadata, Header
from datetime import datetime
from lxml import etree
from lxml.etree import Element
import main
import json
from oai_utils import convert_to_dcat_ap
import logging

import exceptions as exc
from endpoint_handlers import dataset_handler

BASE_URL = "https://sebastien-datalake.cmcc.it/api/v2/datasets/"

# Logging config
logging.basicConfig(level=logging.DEBUG)

# Each method in this class is a verb from the OAI-PMH protocol. Only listRecords is used by the data.europa harvester
class MyMetadataProvider:
    # Method to list records, only method used by data.europa harvester
    def listRecords(self, metadataPrefix='dcat_ap', from_=None, until=None, set=None, scopes=None):
        logging.debug("Fetching data from API")
        # Fetch data from the dataset endpoint
        # TODO: Refactor to fetch from all endpoints, or get data directly if this code is integrated in the data lake system 
        '''
        data = main.fetch_data(
            f"{BASE_URL}{set}"
        )
        '''
        try:
            data = json.dumps(dataset_handler.get_product_details(
                user_roles_names=scopes,
                dataset_id=set,
            ))
        except exc.BaseDDSException as err:
            raise err.wrap_around_http_exception() from err
        
        logging.debug(f"Fetched data: {data}")

        # Convert to RDF graph with proper DCAT-AP fields (URL is being used to fill the accessURL field)
        rdf_graph = convert_to_dcat_ap(data, f"{BASE_URL}{set}")

        # Serialize the RDF graph into a string, 'pretty-xml' format makes it more readable
        rdf_string = rdf_graph.serialize(format='pretty-xml')
        logging.debug(f"RDF string: {rdf_string}")

        # Create a header (mandatory for OAI-PMH)
        header_element = Element("header")
        header = Header(deleted=False, element=header_element, identifier="", datestamp=datetime.utcnow(), setspec=[])

        # Create metadata element and fill it with the RDF/XML string
        metadata_element = Element("metadata")
        metadata = Metadata(element=metadata_element, map={"rdf": rdf_string})
    

        return [(header, metadata, [])], None

    # The remaining methods are only present because they are mandatory for the OAI-PMH protocol
    
    # Minimal implementation for identify
    def identify(self):
        return Identify(
            repositoryName='My Repository',  # Name of the repository
            baseURL='',  # Base URL of the OAI-PMH endpoint
            protocolVersion='2.0',  # OAI-PMH protocol version
            adminEmails=['admin@myserver.com'],  # List of admin email addresses
            earliestDatestamp=datetime(2024, 1, 1),  # Earliest datestamp for records
            deletedRecord='no',  # Policy on deleted records
            granularity='YYYY-MM-DDThh:mm:ssZ',  # Date granularity
            compression=['identity'],  # Supported compression methods
        )

    # Minimal implementation for getRecord
    def getRecord(self, identifier, metadataPrefix='oai_dc'):
        # Create a header
        header = Header(identifier=identifier, datestamp=datetime.now(), setspec=[])

        # Create metadata element (empty in this example)
        metadata = Metadata(element=Element("record"), map={})

        return header, metadata, []

    # Minimal implementation for listIdentifiers
    def listIdentifiers(self, metadataPrefix='oai_dc', from_=None, until=None, set_=None):
        # Create a header
        header = Header(identifier="id1", datestamp=datetime.now(), setspec=[])

        return [header]

    # Minimal implementation for listMetadataFormats
    def listMetadataFormats(self, identifier=None):
        return [('oai_dc', 'http://www.openarchives.org/OAI/2.0/oai_dc.xsd', 'http://www.openarchives.org/OAI/2.0/oai_dc/')]

    # Minimal implementation for listSets
    def listSets(self):
        return []
