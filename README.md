# GCP FinOps Scanner

Local Streamlit app to scan a Google Cloud project for potentially unused or low-usage resources.

It helps you quickly review:

- Unused static external IPs
- Unattached persistent disks
- Snapshot inventory
- Low CPU virtual machines
- Low CPU Cloud SQL instances
- Cloud SQL inventory

The app displays the results in a web UI and lets you download everything as an Excel report.

## How It Works

This project connects to your Google Cloud account using **Application Default Credentials (ADC)** and reads data from:

- Compute Engine API
- Cloud Monitoring API
- Cloud SQL Admin API

The UI is built with Streamlit and runs locally on your machine.

## Requirements

- Python 3.10+ recommended
- A Google Cloud account
- Access to at least one GCP project
- `gcloud` CLI installed

## Connect Your GCP Account

This project uses your local Google Cloud login through ADC.

### 1. Install the Google Cloud CLI

If you do not have it yet, install the Google Cloud SDK / `gcloud` CLI:

https://cloud.google.com/sdk/docs/install

### 2. Log in with your Google account

Open a terminal and run:

```powershell
gcloud auth login
```

This opens a browser so you can sign in to your Google account.

### 3. Create local Application Default Credentials

Run:

```powershell
gcloud auth application-default login
```

This is the most important step for this app.  
It creates local credentials that the Python Google Cloud libraries will use automatically.

### 4. Set your default project

Replace `YOUR_PROJECT_ID` with your GCP project ID:

```powershell
gcloud config set project YOUR_PROJECT_ID
```

You can confirm the active project with:

```powershell
gcloud config get-value project
```

### 5. Enable the required APIs

Make sure these APIs are enabled in your project:

- Compute Engine API
- Cloud Monitoring API
- Cloud SQL Admin API

You can enable them with:

```powershell
gcloud services enable compute.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable sqladmin.googleapis.com
```

### 6. Make sure your account has permission

Your Google account needs permission to view resources and metrics in the target project.

At minimum, you will usually need access that allows you to read:

- Compute Engine resources
- Monitoring metrics
- Cloud SQL instances

If the app returns permission errors, ask your GCP administrator to grant the necessary viewer-level roles for those services.

## Installation

Clone the repository and install the dependencies.

```powershell
git clone <your-repository-url>
cd gcp-orphan-resources2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## How To Use

Start the Streamlit app:

```powershell
streamlit run app.py  
```

If you what to change server address and port 

```powershell
streamlit run app.py  --server.address 127.0.0.1  --server.port 8000
```

Then:

1. Open the local Streamlit page in your browser.
2. Enter your **Project ID** in the left sidebar.
3. Choose the lookback window in days.
4. Adjust the CPU thresholds for VMs and Cloud SQL if needed.
5. Click **Rodar analise**.
6. Review the tables in the UI.
7. Download the Excel report if you want to share the results.

## What Each Report Means

### Unused IPs

Reserved external static IP addresses that are not attached to any resource.

### Unattached Disks

Persistent disks that do not have any attached VM.

### Snapshots

Snapshot inventory with age and source disk reference when available.

### Low CPU VMs

Compute Engine instances with average CPU utilization below the threshold you select during the chosen lookback window.

### Low CPU CloudSQL

Cloud SQL resources with average CPU utilization below the selected threshold.

### CloudSQL Inventory

Basic inventory of Cloud SQL instances in the project.

## Example Workflow

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project my-gcp-project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Inside the app, enter:

- `Project ID`: `my-gcp-project`
- `Lookback`: `7`
- VM CPU threshold: `10%`
- Cloud SQL CPU threshold: `10%`

## Troubleshooting

### `Default credentials not found`

Run:

```powershell
gcloud auth application-default login
```

### `403 Permission denied`

Your account does not have enough permissions in the target project.  
Ask your GCP admin for read access to Compute Engine, Monitoring, and Cloud SQL.

### No data returned

Check:

- The project ID is correct
- The required APIs are enabled
- The project actually contains those resources
- Your account has access to the project

### `gcloud` command not found

Install the Google Cloud CLI first:

https://cloud.google.com/sdk/docs/install

## Project Structure

```text
.
|-- app.py          # Streamlit UI
|-- gcp_scan.py     # GCP data collection and report generation
|-- requirements.txt
|-- README.md
```

## Notes

- This app runs locally and reads data from your Google Cloud environment.
- It does not create, modify, or delete resources.
- Review findings before taking action on any resource flagged as unused or low usage.
