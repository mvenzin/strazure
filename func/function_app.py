import azure.functions as func
import logging
import os
import json
import datetime
import pyodbc
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from stravalib.client import Client as StravaClient
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient


from get_kv_client import get_kv_client
from get_strava_client import get_strava_client
from get_sql_conn import get_sql_conn
from get_blob_client import get_blob_client
from get_activities_and_store_in_db_and_storage import initialize, get_activity_from_strava, add_activity_to_storage, add_activity_to_db, delete_activity_from_db, delete_activity_from_storage


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)



# 1) HTTP-triggered webhook endpoint (GET validation + POST events)
@app.function_name(name="StravaWebhook")
@app.route(route="strava-webhook", methods=["GET", "POST"])
@app.queue_output(arg_name="activity_queue", queue_name="strava-activity", connection="AzureWebJobsStorage")
def strava_webhook(req: func.HttpRequest, activity_queue: func.Out[str]) -> func.HttpResponse:
    if req.method == "GET":
        # Subscription validation
        challenge = req.params.get("hub.challenge")
        verify_token = req.params.get("hub.verify_token")
        expected = "STRAVA" #os.environ.get("STRAVA_VERIFY_TOKEN")

        if expected and verify_token != expected:
            return func.HttpResponse("Bad verify_token", status_code=403)

        body = {"hub.challenge": challenge or ""}
        return func.HttpResponse(json.dumps(body), mimetype="application/json", status_code=200)

    if req.method == "POST":
        try:
            evt = req.get_json()
        except ValueError:
            return func.HttpResponse("Invalid JSON", status_code=400)

        # Acknowledge FAST; do work asynchronously
        # Enqueue the raw event for processing
        activity_queue.set(json.dumps(evt))
        return func.HttpResponse(status_code=200)

    return func.HttpResponse(status_code=405)

# 2) Queue-triggered processor (does the heavy work)
@app.function_name(name="StravaActivityProcessor")
@app.queue_trigger(arg_name="msg", queue_name="strava-activity", connection="AzureWebJobsStorage")
def strava_activity_processor(msg: func.QueueMessage) -> None:
    raw = msg.get_body().decode("utf-8")
    evt = json.loads(raw)
    logging.info("Processing Strava event: %s", raw)

    if evt.get("object_type") != "activity":
        logging.info("Skipping non-activity event.")
        return

    # processing events based on type

    if evt.get("aspect_type") == "delete":
        delete_activity_from_db(evt.get("object_id"))
        delete_activity_from_storage(evt.get("object_id"))
        logging.info(f"Deleted activity ID {evt.get('object_id')}.")

    if evt.get("aspect_type") == "create":
        activity_id = evt.get("object_id")
        logging.info(f"Fetching full data for activity ID {activity_id} from Strava.")
        activity_data, activity_json = get_activity_from_strava(activity_id)
        add_activity_to_db(activity_data)
        add_activity_to_storage(activity_json)

    if evt.get("aspect_type") == "update":
        delete_activity_from_db(evt.get("object_id"))
        delete_activity_from_storage(evt.get("object_id"))
        activity_id = evt.get("object_id")
        logging.info(f"Fetching full data for activity ID {activity_id} from Strava.")
        activity_data, activity_json = get_activity_from_strava(activity_id)
        add_activity_to_db(activity_data)
        add_activity_to_storage(activity_json)    




@app.route(route="http_trigger")
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')

    if name != 'initialize':
        logging.exception(f"Unexpected name parameter: {name}")
        return func.HttpResponse("Invalid request. The 'name' parameter must be 'initialize'.", status_code=400)
    
    try:
        initialize()
        return func.HttpResponse(f"Activities DB and Storage successfully initialized.")
    except Exception as e:
        logging.error(f"Error during Strava data update process: {e}")
        return func.HttpResponse("Error during Strava data update process.", status_code=500)


    
