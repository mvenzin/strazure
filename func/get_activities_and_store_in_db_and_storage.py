import azure.functions as func
import os
import json
import datetime
import logging
from azure.storage.blob import ContainerClient
import pyodbc

from get_kv_client import get_kv_client
from get_strava_client import get_strava_client
from get_sql_conn import get_sql_conn
from get_blob_client import get_blob_client

# Fetch new activities since last accessed activity and store them in the database
def to_mapping(obj):
    if isinstance(obj, dict):                 # already a dict
            return obj
    if hasattr(obj, "model_dump"):            # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):                  # Pydantic v1
        return obj.dict()
    if hasattr(obj, "to_dict"):               # e.g., stravalib models
        return obj.to_dict()
    return vars(obj)    

def bundle(activity, stream):
    return {
        'id' : activity.get('id'),
        'activity' : activity,
        'stream' : stream
    }  

def insert_to_db(cursor, conn, activity_data):
    sql_insert_query = """
        INSERT INTO dbo.StravaActivity_bronze (
        id, athlete_id, name, description, sport_type, type,
        start_date, start_date_local, timezone, utc_offset,
        distance, moving_time, elapsed_time, total_elevation_gain,
        average_speed, average_heartrate, device_name, visibility,
        upload_id, external_id, map_summary_polyline
        ) VALUES (
        ?,?,?,?,?,?,
        ?,?,?,?,?,?,
        ?,?,?,?,?,?,
        ?,?,?
        );
        """
    sql_insert_values = [
        activity_data.get('id'),
        activity_data.get('athlete_id'),
        activity_data.get('name'),
        activity_data.get('description'),
        activity_data.get('sport_type'),
        activity_data.get('type'),
        activity_data.get('start_date').isoformat(),
        activity_data.get('start_date_local').isoformat(),
        activity_data.get('timezone'),
        activity_data.get('utc_offset'),
        activity_data.get('distance'),
        activity_data.get('moving_time'),
        activity_data.get('elapsed_time'),
        activity_data.get('total_elevation_gain'),
        activity_data.get('average_speed'),
        activity_data.get('average_heartrate'),
        activity_data.get('device_name'),
        activity_data.get('visibility'),
        activity_data.get('upload_id'),
        activity_data.get('external_id'),
        activity_data.get('map').get('summary_polyline')]
    
    try:
        cursor.execute(sql_insert_query, sql_insert_values)
        conn.commit()
        logging.info(f"Inserted activity ID {activity_data.get('id')} into the database.")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error inserting activity ID {activity_data.get('id')} into the database: {e}")
    return
    
    
def initialize():
    strava_client = get_strava_client()
    conn = get_sql_conn()
    cursor = conn.cursor()
    

    #initialize database
    sql_str = """ drop table if exists dbo.StravaActivity_bronze;
    CREATE TABLE dbo.StravaActivity_bronze (
        id BIGINT NOT NULL PRIMARY KEY,
        athlete_id BIGINT NULL,
        name NVARCHAR(255) NULL,
        description NVARCHAR(2000) NULL,
        sport_type NVARCHAR(50) NULL,
        type NVARCHAR(50) NULL,
        start_date DATETIME2 NULL,
        start_date_local DATETIME2 NULL,
        timezone NVARCHAR(64) NULL,
        utc_offset INT NULL,
        distance FLOAT NULL,
        moving_time INT NULL,
        elapsed_time INT NULL,
        total_elevation_gain FLOAT NULL,
        elev_high FLOAT NULL,
        elev_low FLOAT NULL,
        average_speed FLOAT NULL,
        max_speed FLOAT NULL,
        average_heartrate FLOAT NULL,
        max_heartrate FLOAT NULL,
        average_cadence FLOAT NULL,
        calories FLOAT NULL,
        has_heartrate BIT NULL,
        commute BIT NULL,
        trainer BIT NULL,
        manual BIT NULL,
        private BIT NULL,
        visibility NVARCHAR(20) NULL,
        device_name NVARCHAR(100) NULL,
        gear_id NVARCHAR(50) NULL,
        external_id NVARCHAR(100) NULL,
        upload_id BIGINT NULL,
        upload_id_str NVARCHAR(50) NULL,
        achievement_count INT NULL,
        kudos_count INT NULL,
        comment_count INT NULL,
        athlete_count INT NULL,
        photo_count INT NULL,
        total_photo_count INT NULL,
        start_latlng NVARCHAR(64) NULL,
        end_latlng NVARCHAR(64) NULL,
        [map_summary_polyline] NVARCHAR(MAX) NULL,
    );"""

    try:
        cursor.execute(sql_str)
        conn.commit()
        logging.info("Initialized StravaActivity_bronze table in the database.")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error initializing StravaActivity_bronze table: {e}")
        return
    
    #fetch all activities and store them in the database and storage

    try:
        # Fetch all activities since the beginning
        activities = strava_client.get_activities()

        for activity in activities:
            logging.info(f"Processing activity ID {activity}")
            activity_id =getattr(activity, 'id')
            activity_streams = strava_client.get_activity_streams(activity_id, types=['time', 'latlng', 'distance'])
            activity_data = to_mapping(activity) 
            logging.info(f"Activity start date: {activity_data.get('start_date')}")
            activity_data['streams'] = to_mapping(activity_streams)
            activity_json = bundle(activity_data, activity_data['streams'])

            logging.info(f"Fetched activity ID {activity_id} with streams.")

            blob_name = f"activity/{activity_id}.json"

            logging.info(f"Prepared activity data for activity ID {activity_id}.")
            
            add_activity_to_storage(activity_json, blob_name)

            # Insert activity data into the database
            add_activity_to_db(activity_data)

        return func.HttpResponse(f"Initialized Strava activities in DB and Storage successfully.")

    except Exception as e:
        logging.error(f"Error initializing Strava data: {e}")
        return func.HttpResponse("Error initializing Strava data.", status_code=500)
    

def delete_activity_from_db(activity_id):
    conn = get_sql_conn()
    cursor = conn.cursor()
    sql_delete_query = "DELETE FROM dbo.StravaActivity_bronze WHERE id = ?;"
    try:
        cursor.execute(sql_delete_query, (activity_id,))
        conn.commit()
        logging.info(f"Deleted activity ID {activity_id} from the database.")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error deleting activity ID {activity_id} from the database: {e}")
    return

def delete_activity_from_storage(activity_id):
    storage_client = get_blob_client()
    blob_name = f"activity/{activity_id}.json"
    try:
        storage_client.delete_blob(blob_name)
        logging.info(f"Deleted activity ID {activity_id} from Blob Storage.")
    except Exception as e:
        logging.error(f"Error deleting activity ID {activity_id} from Blob Storage: {e}")
    return

def add_activity_to_db(activity_data):
    conn = get_sql_conn()
    cursor = conn.cursor()
    try:
        insert_to_db(cursor, conn, activity_data)
        logging.info(f"Added activity ID {activity_data.get('id')} to the database.")
    except Exception as e:
        logging.error(f"Error adding activity ID {activity_data.get('id')} to the database: {e}")
    return

def add_activity_to_storage(activity_json, blob_name=None):
    storage_client = get_blob_client()
    activity_id = activity_json.get('id')
    if not blob_name:
        blob_name = f"activity/{activity_id}.json"
    try:
        storage_client.upload_blob(name=blob_name, data=json.dumps(activity_json, default=lambda o: o.isoformat() if isinstance(o, (datetime.datetime, datetime.date)) else str(o),
                                                 ensure_ascii=False, separators=(",", ":")), overwrite=True)
        logging.info(f"Added activity ID {activity_id} to Blob Storage as {blob_name}.")
    except Exception as e:
        logging.error(f"Error adding activity ID {activity_id} to Blob Storage: {e}")
    return

def get_activity_from_strava(activity_id):
    #connect to strava and fetch activity by id:
    try:
        strava_client = get_strava_client()
        activity = strava_client.get_activity(activity_id)
        activity_streams = strava_client.get_activity_streams(activity_id, types=['time', 'latlng', 'distance'])
        activity_data = to_mapping(activity) 
        activity_data['streams'] = to_mapping(activity_streams)
        activity_json = bundle(activity_data, activity_data['streams'])
        logging.info(f"Fetched activity ID {activity_id} from Strava.")
        return (activity_data, activity_json)
    
    except Exception as e:
        logging.error(f"Error fetching activity ID {activity_id} from Strava: {e}")
        return (None, None)