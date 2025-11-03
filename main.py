import pandas as pd
import requests
import os
import duckdb
from dotenv import find_dotenv, load_dotenv

# Load environment variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# assign variable
COMPLETE_PARQUET = os.getenv("COMPELTE_PARQUET_URL")   
DAILY_PARQUET = os.getenv("DAILY_PARQUET_URL")
RETENTION_PARQUET = os.getenv("RETENTION_PARQUET_URL")
RATE_PARQUET = os.getenv("RATE_PARQUET_URL")

#create db path
db_path = ".\\blood_data.duckdb"
con = duckdb.connect(db_path)

parquet_files = {
    "historical": COMPLETE_PARQUET,
    "daily": DAILY_PARQUET,
    "retention": RETENTION_PARQUET,
    "rate": RATE_PARQUET,
}

# download, read, and store each parquet into db
for table_name, parquet_url in parquet_files.items():
    print(f"Downloading and loading {table_name}...")

   
    file_path = f"temp_{table_name}.parquet"

    # download parquet file
    response = requests.get(parquet_url)
    response.raise_for_status()
    with open(file_path, "wb") as f:
        f.write(response.content)

    # read file
    df = pd.read_parquet(file_path, engine="pyarrow")

    # load into DuckDB
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")

    # delete temp file to save space
    os.remove(file_path)

    print(f" {table_name} loaded successfully ({len(df)} rows)")

con.close()
print("All parquet files loaded into DuckDB database:", db_path)