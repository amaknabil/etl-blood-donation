import os
import duckdb
from dotenv import load_dotenv,find_dotenv
from pathlib import Path

env_path = find_dotenv()
load_dotenv(env_path)

historical_url = os.getenv("COMPLETE_PARQUET_URL")
retention_url = os.getenv("RETENTION_PARQUET_URL")
donnorrate_url = os.getenv("RATE_PARQUET_URL")

db_path = os.getenv("DUCKDB_FILE_PATH") 

def add_table(con,csv,table):
    BASE_DIR = Path(__file__).parent
    csv_path = BASE_DIR / 'data' / csv
    str_csv = str(csv_path)
    try:
        print(f"Loading table for {table}\n")
        query = f"CREATE OR REPLACE TABLE {table} as SELECT * FROM read_csv('{str_csv}') "
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



def load_transformed_retention_to_db(con,url,table):
        try:
            query = f"""
                        create or replace table {table} as
                        select *, 
                        lag(visit_date,1,visit_date) over(w) as previous_visit,
                        lead(visit_date,1,visit_date) over(w) as next_visit,
                        date_diff('day', LAG(visit_date) OVER w, visit_date) AS days_diff,
                        case
                            when lag(visit_date) over w is null then 'First Visit'
                            when lead(visit_date) over w is null then 'Last Visit'
                            else 'Returning'
                        end as visit_status,
                        row_number() over (partition by donor_id order by visit_date) as nth_visit,
                        year(visit_date) - birth_date as age
                        from read_parquet('{url}')
                        window w as (partition by donor_id order by visit_date)
                        order by donor_id,visit_date 
                    """
            print(f"Starting to loading data into table {table}")
            con.execute(query)
            print(f"Successfully loaded data into table {table} \n")
        except Exception as e:
            print(f"Fail to full load on table {table} because : {e}")

def load_transformed_historical_to_db(con, url, table):
    try:
        print(f"Starting to load data into table {table}...")
        
        query = f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT 
                inst_code,
                CAST(visit_date AS DATE) as visit_date,
                CAST(NULLIF(previous_visit, '1800-08-10') AS DATE) as previous_visit,
                (CAST(visit_date AS DATE) - CAST(NULLIF(previous_visit, '1800-08-10') AS DATE)) as days_since_last,
                CASE 
                    WHEN previous_visit = '1800-08-10' THEN TRUE 
                    ELSE FALSE 
                END as is_first_visit,
                donation_type,
                donation_location,
                classification_id,
                blood_group
            FROM read_parquet('{url}')
            ORDER BY visit_date
        """
        
        # Execute the transformation
        con.execute(query)

    except Exception as e:
        # 4. Correctly capture the specific error 'e'
        print(f"Fail to full load on table {table} because: {e}")
        raise e  # Re-raise the error so the flow knows it failed

def load_transformed_donorrate_to_db(con,url,table):
        try:
            query = f""" create or replace table {table}  as select *,year(latest) - birth_date as age from read_parquet('{url}') order by latest desc """
            print(f"Starting to loading data into table {table}")
            con.execute(query)
            print(f"Successfully loaded data into table {table} \n")
        except Exception as e:
            print(f"Fail to full load on table {table} because : {e}")


try:
    print(f"Connecting to {db_path}")
    con = duckdb.connect(db_path)
    print(f"Successfully connected to {db_path}\n")
    add_table(con,'inst_code.csv','inst_code')
    add_table(con,'race.csv','race')
    load_transformed_historical_to_db(con,historical_url,'historical')
    load_transformed_retention_to_db(con,retention_url,'retention')
    load_transformed_donorrate_to_db(con,donnorrate_url,"donorrate")
    
    query = "CREATE or replace TABLE malaysia_states AS SELECT * FROM ST_Read('https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MYS/ADM1/geoBoundaries-MYS-ADM1_simplified.geojson')"
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