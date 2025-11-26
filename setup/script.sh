#!/usr/bin/env bash

set -euo pipefail

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..


brew tap hashicorp/tap
brew install hashicorp/tap/terraform
brew update && brew install azure-cli

az login
az account list
read -s -p "Please copy-paste the subscription ID (id) you want to use: " subscription_id
az account set --subscription "$subscription_id"

read -r ARM_CLIENT_ID ARM_CLIENT_SECRET ARM_TENANT_ID < <(
  az ad sp create-for-rbac \
    --role "Contributor" \
    --scopes "/subscriptions/$subscription_id" \
    --query "[appId,password,tenant]" -o tsv
)
export ARM_CLIENT_ID ARM_CLIENT_SECRET ARM_TENANT_ID ARM_SUBSCRIPTION_ID="$subscription_id"


python3 setup/get_secrets.py
export TF_VAR_secrets="$(< secrets.json)"


read -s -p "Please insert a database username:" db_username
echo
read -s -p "Please insert a database password:" db_password
echo
read -s -p "Please indicate your home-ip address so you can access the db from home:" home_ip
echo

export TF_VAR_db_username="$db_username"
export TF_VAR_db_password="$db_password"
export TF_VAR_home_ip="$home_ip"

cd infra
echo "Now we set up the infrastructure"
terraform apply -auto-approve
FUNCTION_APP_NAME="$(terraform output -raw function_app_name)"
echo "${FUNCTION_APP_NAME}"
cd ..
cd func
echo "Now we deploy the function ${FUNCTION_APP_NAME}."
func azure functionapp publish "$FUNCTION_APP_NAME" 
az functionapp restart -g strava_resources -n $FUNCTION_APP_NAME
sleep 20
echo "We start downloading all past activities, this may take a while."
open https://${FUNCTION_APP_NAME}.azurewebsites.net/api/http_trigger?name=initialize

cd ..
echo "It should now be downloading all your past activities..."
echo 
echo "It remains to create the webhook so that your activities get synced automatically. For details, check https://developers.strava.com/docs/webhooks/ . If this step failed, it might be that you already have a subscription. "
echo "${FUNCTION_APP_NAME}"
echo "$(jq -r .client_id secrets.json)"
echo "$(jq -r .client_secret secrets.json)"

curl -X POST https://www.strava.com/api/v3/push_subscriptions -F client_id=$(jq -r .client_id secrets.json) -F client_secret=$(jq -r .client_secret secrets.json) -F callback_url=https://${FUNCTION_APP_NAME}.azurewebsites.net/api/strava-webhook -F verify_token=STRAVA
echo "Subscription created. Or not, see message above - check last part in README."
echo "Everything set up: All past activities are in the database. All new activities will automatically be updated. "



