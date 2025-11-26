import azure.functions as func
from stravalib.client import Client as StravaClient
import logging
import json
from get_kv_client import get_kv_client

def get_strava_client():
    """gets a valid strava client by refreshing the access tokens. the new toksens are stored back in the key vault"""
    try:
        strava_client = StravaClient()
        try:
            kv_client = get_kv_client()
        except Exception as e:
            logging.error(f"Error getting Key Vault client: {e}")
            return func.HttpResponse("Error getting Key Vault client.", status_code=500)

        strava_secret = json.loads(kv_client.get_secret("secrets").value)

        new_access_tokens = strava_client.refresh_access_token(
            client_id=strava_secret['client_id'],
            client_secret=strava_secret['client_secret'],
            refresh_token=strava_secret['token']['refresh_token']
        )

        logging.info("Refreshed Strava access token successfully."f" New access token: {new_access_tokens}")

        strava_secret['token'] = new_access_tokens

        kv_client.set_secret("secrets", json.dumps(strava_secret))
                                           
        strava_client = StravaClient(access_token=strava_secret['token']['access_token'])
        
        return strava_client

    except Exception as e:
        logging.error(f"Error creating valid strava_client: {e}")
        return func.HttpResponse("Error refreshing Strava access token.", status_code=500)