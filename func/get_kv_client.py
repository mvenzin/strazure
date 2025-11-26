import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import json
import os
import logging

def get_kv_client():
    try:
        keyvault_uri = os.environ.get("KEYVAULT_URI")
        az_client = SecretClient(vault_url=keyvault_uri, credential=DefaultAzureCredential())
        return az_client
        
        
    except Exception as e:
        logging.error(f"Error connecting to Key Vault: {e}")
        return func.HttpResponse("Error connecting to Key Vault.", status_code=500)