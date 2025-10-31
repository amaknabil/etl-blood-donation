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


