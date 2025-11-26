import azure.functions as func
import logging
import pyodbc
import os

def get_sql_conn():
    conn_str = os.environ.get("SQL_CONNECTION_STRING")
    try:
        logging.info(f"Database connection string: {conn_str}")
        conn = pyodbc.connect(conn_str)
        return conn
    
    except Exception as e:
        logging.info(f"Error connecting to the database: {e}")
        return func.HttpResponse(
            "Error connecting to the database.",
            status_code=500
        )