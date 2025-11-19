import os
import duckdb
from dotenv import load_dotenv,find_dotenv

env_path = find_dotenv()
load_dotenv(env_path)

historical_url = "./temp_data/donation.parquet"
retention_url = "./temp_data/retention.parquet"
donnorrate_url = "./temp_data/donnorrate.parquet"

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
        query = f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM '{url}'"
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


    
    print("Successfully load all data to each tables")

    con.close()
    print("close db")
# hi
except Exception as e:
    print(f"Fail because: {e}")