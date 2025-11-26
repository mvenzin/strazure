from azure.storage.blob import ContainerClient 
from azure.identity import DefaultAzureCredential
import os

import logging

def get_blob_client():
    try:
        uri = os.environ.get("RAWDATA_STORAGE_URI")
        container = os.environ.get("RAWDATA_CONTAINER_NAME")
        return ContainerClient(account_url=uri, container_name=container, credential=DefaultAzureCredential())
    except Exception as e:
        logging.error(f"Error connecting to Blob Storage: {e}")
        return None
        