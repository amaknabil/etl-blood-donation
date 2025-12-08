##  About

This project is an **Extract, Transform, Load (ETL)** pipeline built with **Python**, designed to process **historical blood donation data** efficiently.

The ETL process performs the following key functions:

- **Extract:** Retrieves raw data from a remote **Parquet file (via URL)**.  
- **Transform:** Cleans, formats, and processes the data using **Pandas**.  
- **Load:** Stores the cleaned dataset into a local **DuckDB** database for easy querying and analysis.

---

## Installation

Here’s how you can run the project locally:

1. **Clone this repository**
    ```sh
    git clone https://github.com/amaknabil/etl-blood-donation.git
    ```

2. **Go into the project root directory**
    ```sh
    cd etl-blood-donation
    ```

3. **Copy the environment file**
    ```sh
    cp .env.example .env
    ```
    > Update the `.env` file with your own configuration if needed.

4. **Create a virtual Python environment**
    ```sh
    python -m venv venv
    ```

5. **Activate the virtual environment**
    - **Windows**
        ```sh
        venv\Scripts\activate
        ```
    - **macOS/Linux**
        ```sh
        source venv/bin/activate
        ```

6. **Install dependencies**
    ```sh
    pip install -r requirements.txt
    ```

---

## Deployment in Cloud
Here’s how you can run the project in Ubuntu Server:

1. **Prepare Server**
    ```sh
    sudo apt-get update
    ```
    ```sh
    sudo apt-get install -y python3-pip python3-venv git
    ```
2. **Clone**
    ```sh
    cd /home/ubuntu
    ```
    ```sh
    git clone https://github.com/amaknabil/etl-blood-donation.git
    ```
    ```sh
    cd etl-blood-donation
    ```
    ```sh
    python3 -m venv venv
    ```
    ```sh
    source venv/bin/activate
    ```
    ```sh
    pip install -r requirements.txt
    ```
3. **Configure .env File**
Create the .env file on the server. Do not commit this file to Git.
    ```sh
    cp .env.example .env
    ```
    > Update the `.env` file with your own configuration if needed.
4. **Create a service to run the Prefect UI and API.**
    ```sh
    sudo nano /etc/systemd/system/prefect_server.service
    ```
Paste the following configuration: (Replace <YOUR_SERVER_IP> with your VM's public IP)
    ```sh
    [Unit]
    Description=Prefect Server (UI + API)
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/home/ubuntu/etl-blood-donation

    # Start server listening on all interfaces
    ExecStart=/home/ubuntu/etl-blood-donation/venv/bin/prefect server start --host 0.0.0.0

    Restart=always
    RestartSec=10

    # Set API URL for the UI to connect correctly
    Environment="PREFECT_UI_API_URL=http://<YOUR_SERVER_IP>:4200/api"

    [Install]
    WantedBy=multi-user.target
    ```
5. **Create a service to run your Python flow script.**
    ```sh
    sudo nano /etc/systemd/system/blood_etl.service
    ```
Paste the following configuration:
    ```sh
    [Unit]
    Description=Blood Donation ETL Prefect Worker
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/home/ubuntu/etl-blood-donation

    # 1. Add project root to PYTHONPATH
    Environment="PYTHONPATH=/home/ubuntu/etl-blood-donation"

    # 2. Tell worker to talk to the local Prefect Server
    Environment="PREFECT_API_URL=[http://127.0.0.1:4200/api](http://127.0.0.1:4200/api)"

    # 3. Run the flow
    ExecStart=/home/ubuntu/etl-blood-donation/venv/bin/python flows/blood_donation_flow.py

    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```
6. Activate and Run
Reload systemd configs
    ```sh
    sudo systemctl daemon-reload
    ```

Start Server
    ```sh
    sudo systemctl enable --now prefect_server
    ```

Start Worker
    ```sh
    sudo systemctl enable --now blood_etl
    ```

7. **Verification and Logs**
    ```sh
    journalctl -u blood_etl -f
    ```










