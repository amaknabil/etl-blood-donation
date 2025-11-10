import os
import duckdb
from dotenv import load_dotenv,find_dotenv

env_path = find_dotenv()
load_dotenv(env_path)

historical_url = os.getenv("COMPLETE_PARQUET_URL")
retention_url = os.getenv("RETENTION_PARQUET_URL")
donnorrate_url = os.getenv("RATE_PARQUET_URL")

db_path = os.getenv("DUCKDB_FILE_PATH") 

def add_table(con,csv,table):
    try:
        print(f"Loading table for {table}\n")
        query = f"CREATE OR REPLACE TABLE {table} as SELECT * FROM read_csv('{csv}') "
        con.execute(query)
        print(f"successful added table {table}\n")
    except Exception as e:
        print(f"Fail for {table} because :{e} ")
    

def load_data_to_db(con,url,table):
    try:
        query = f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}')"
        print(f"Starting to loading data into table {table}")
        con.execute(query)
        print(f"Successfully loaded data into table {table} \n")
    except Exception as e:
        print(f"Fail to full load on table {table} because : {e}")

try:
    print(f"Connecting to {db_path}")
    con = duckdb.connect(db_path)
    print(f"Successfully connected to {db_path}\n")
    load_data_to_db(con,historical_url,'historical')
    load_data_to_db(con,retention_url,'retention')
    load_data_to_db(con,donnorrate_url,"donorrate")
    add_table(con,'.\\data\\inst_code.csv','inst_code')
    add_table(con,'.\\data\\race.csv','race')


    
    query = "CREATE TABLE malaysia_states AS SELECT * FROM ST_Read('https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MYS/ADM1/geoBoundaries-MYS-ADM1_simplified.geojson')"
    print("Adding Malaysia_states table")
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(query)
    print("Successfully added Malaysia_states table\n")
    print("Successfully load all data to each tables")

    con.close()
    print("close db")

except Exception as e:
    print(f"Fail because: {e}")