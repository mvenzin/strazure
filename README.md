# 🚴‍♂️ Strava Activity Scraper (Cloud-Native, Fully Automated)

This project automatically pulls Strava activities, stores them in the cloud, and keeps them up to date. Everything is **end-to-end automated**, from infrastructure provisioning to webhook wiring and database initialization.

It is intended to demonstrate:

- Cloud & serverless architecture
- Infrastructure as Code (IaC) with **Terraform**
- Secure secret management with **Azure Key Vault**
- Automated deployment via a **custom Bash bootstrap script**
- Integration with a third-party API (Strava) using webhooks + OAuth2
- Database design and initialization for analytics

---

## High-Level Overview

1. A **custom Bash script**:
   - Guides you through the Strava setup (API app, client ID/secret, webhook details)
   - Provisions cloud resources with Terraform
   - Deploys the scraper/function code
   - Initializes the SQL database schema and fills it with your past activities
   - Connects Strava webhooks to the cloud function

2. A **serverless Function** (Azure Function):
   - A webhook endpoint for Strava activity updates (create, delete, update)
   - A http trigger to reset the SQL database

3. A **cloud SQL database and Blob storage**:
   - stores normalized activity data in an SQL database ready to be queried
   - stores full activities to be accessible whenever needed

---

## Components

- **Infrastructure** (see `infra/`)
  - Terraform configurations
  - Key Vault, Function App, SQL Database, Storage, Role Assignments, etc.

- **Application** (see `func/`)
  - Strava webhook handler
  - Activity fetcher / backfill logic
  - Database layer (migrations + schema initialization)

- **Automation** (run `setup/`)
  - Sets up environment
  - Connects to Strava and Azure to authenticate
  - Prompts for necessary information (SQL-login, home IP address to query database, etc.)
  - Collects Strava API info (client tokens, etc.)
  - Runs Terraform to set up infrastructure
  - Manages secrets to be stored safely (Key Vault)
  - Deploys the code
  - Initializes the database (creates tables, fetches past activities)
  - Registers the Strava webhooks


## Prerequisites

Before running the project you’ll need:

- A **Strava account** (ideally with some activities ;) )
- A **Strava API application** (created via Strava’s developer portal)
- A cloud account (e.g. **Azure**) with:
  - Permissions to create resource groups, Key Vaults, Function Apps, SQL DBs, etc.
- Locally:
  - Brew
  - Bash
  - Terraform
  - Azure CLI
  - Python

---

## Quick Start

The easiest way to get everything running is via the terminal:

```cd setup            ```
```bash script.sh      ```

You will be prompted for the necessary logins and authorizations. For the Strava authorization, the browser will open automatically for you to do the necessary confirmations (log-in and authorize selection).

## Troubleshooting

Two edges cases are worth pointing out.

**Setting up the SQL database**
The SQL database enforces a specific password policy. It must be > 8 characters long, and contain upper and lower case characters, including numbers and special characters (\*!% ...). The IP address (for access rights) has to be of valid format. If you want to set this up later, use 0.0.0.0 . If these values are set incorrectly, Terraform won't be able to provision the resources and the script has to be run again.

**Initializing the database and wiring up the webhook**
After deploying the function app, it may take a while for the function to be fully live. This can be an issue for creating an API subscription (webhook) since Strava requires an immediate response. When the script is executed, you'll see whether it was successful. 
If not, get the function-app's name from Azure Portal (strava-function-app-{random_8_digits}), and Strava's client id and client secret from Strava (from https://www.strava.com/settings/api). Replace these values into the corresponding `< ... >`'s and run
`curl -X POST https://www.strava.com/api/v3/push_subscriptions -F client_id=<your_client_id> -F client_secret=<your_client_secret> -F callback_url=https://<your_function_apps_name>.azurewebsites.net/api/strava-webhook -F verify_token=STRAVA`
If there remain some issues, check https://developers.strava.com/docs/webhooks/

