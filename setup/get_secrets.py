import json
import os
import json
from selenium import webdriver
import time
import re
from stravalib.client import Client

def get_secrets():
    print('This is the first time you use this. Please login to https://www.strava.com/settings/api and create a new application. ')
        
    client_id = input(f"Please enter your client id: ")
    client_secret = input(f"Please enter your client secret: ")
    
    client = Client()
    request_scope = ["read_all", "profile:read_all", "activity:read_all"]
    redirect_url = "http://127.0.0.1:5000/authorization"

    # Creates an authorization URL using stravalib
    url = client.authorization_url(
        client_id=client_id,
        redirect_uri=redirect_url,
        scope=request_scope,
    )

    print("A browser window will open for you to login to Strava and authorize the application.")

    # Opens the URL and automatically gets the necessary code
    driver = webdriver.Firefox()
    driver.get(url)
    match = re.search(r"authorization?state=&code=([^&]+)", driver.current_url)
    while not match:
        time.sleep(0.5)
        match = re.search(r"code=([^&]+)", driver.current_url)
    code = match.group(1)
    driver.close()

    #Exchanges the code for an access token. Token is stored in json-file.
    client = Client()
    token_response = client.exchange_code_for_token(client_id=client_id, client_secret=client_secret, code=code)

    data = {'client_id': client_id,
            'client_secret': client_secret,
            'token': token_response
            }

    
    with open("secrets.json", "w+") as file:
        file.seek(0)
        file.truncate()
        json.dump(data, file, indent=4)

   

if __name__ == "__main__":
    get_secrets()