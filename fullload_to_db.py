import os
import duckdb
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

env_path = find_dotenv()
load_dotenv(env_path, override=True)

historical_url = os.getenv("COMPLETE_PARQUET_URL")
retention_url = os.getenv("RETENTION_PARQUET_URL")
donnorrate_url = os.getenv("RATE_PARQUET_URL")
population_url = os.getenv("POPULATION_URL")

db_path = os.getenv("DUCKDB_FILE_PATH") 

# Optimized config for 1GB RAM
config = {
    "memory_limit": "256MB",  # Reduce memory limit
    "temp_directory": "./duck_temp",  # Ensure temp directory exists
    "max_temp_directory_size": "2GB",  # Increase temp directory size
    "threads": 1, 
    "preserve_insertion_order": False
}

def add_table(con, csv, table):
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

def load_data_in_batches(con, url, table, batch_size=100000):
    """Load data in batches to reduce memory usage"""
    try:
        print(f"Starting to load data into table {table} in batches...")
        
        # First, get total row count
        count_query = f"SELECT COUNT(*) as total_rows FROM read_parquet('{url}')"
        result = con.execute(count_query).fetchone()
        total_rows = result[0] if result else 0
        print(f"Total rows to process: {total_rows}")
        
        # Create empty table with schema
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}') LIMIT 0")
        
        # Load in batches
        for offset in range(0, total_rows, batch_size):
            batch_query = f"""
                INSERT INTO {table} 
                SELECT * FROM read_parquet('{url}') 
                LIMIT {batch_size} OFFSET {offset}
            """
            con.execute(batch_query)
            rows_loaded = min(offset + batch_size, total_rows)
            print(f"  Loaded {rows_loaded}/{total_rows} rows ({rows_loaded/total_rows*100:.1f}%)")
        
        print(f"Successfully loaded data into table {table} \n")
    except Exception as e:
        print(f"Fail to load on table {table} because: {e}")
        raise e

def load_transformed_historical_to_db(con, url, table, batch_size=50000):
    """Load and transform historical data in batches"""
    try:
        print(f"Starting to load data into table {table}...")
        
        # First, get total row count
        count_query = f"SELECT COUNT(*) as total_rows FROM read_parquet('{url}')"
        result = con.execute(count_query).fetchone()
        total_rows = result[0] if result else 0
        print(f"Total rows to process: {total_rows}")
        
        # Create empty table with schema
        create_table_query = f"""
            CREATE OR REPLACE TABLE {table} (
                inst_code VARCHAR,
                visit_date DATE,
                previous_visit DATE,
                days_since_last INTEGER,
                is_first_visit BOOLEAN,
                donation_type VARCHAR,
                donation_location VARCHAR,
                classification_id VARCHAR,
                blood_group VARCHAR
            )
        """
        con.execute(create_table_query)
        
        # Load and transform in batches
        for offset in range(0, total_rows, batch_size):
            batch_query = f"""
                INSERT INTO {table} 
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
                LIMIT {batch_size} OFFSET {offset}
            """
            con.execute(batch_query)
            rows_loaded = min(offset + batch_size, total_rows)
            print(f"  Loaded {rows_loaded}/{total_rows} rows ({rows_loaded/total_rows*100:.1f}%)")
        
        print(f"Successfully loaded data into table {table} \n")
    except Exception as e:
        print(f"Fail to full load on table {table} because: {e}")
        raise e

def load_transformed_retention_to_db(con, url, table, batch_size=50000):
    """Load retention data in batches"""
    try:
        print(f"Starting to load data into table {table}...")
        
        # Get total row count
        count_query = f"SELECT COUNT(*) as total_rows FROM read_parquet('{url}')"
        result = con.execute(count_query).fetchone()
        total_rows = result[0] if result else 0
        print(f"Total rows to process: {total_rows}")
        
        # Create empty table
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}') LIMIT 0")
        
        # Load in batches
        for offset in range(0, total_rows, batch_size):
            batch_query = f"""
                INSERT INTO {table} 
                SELECT * FROM read_parquet('{url}') 
                LIMIT {batch_size} OFFSET {offset}
            """
            con.execute(batch_query)
            rows_loaded = min(offset + batch_size, total_rows)
            print(f"  Loaded {rows_loaded}/{total_rows} rows ({rows_loaded/total_rows*100:.1f}%)")
        
        # Sort after loading - WITHOUT using TEMP TABLE
        print("Sorting data by donor_id and visit_date...")
        sort_query = f"""
            CREATE OR REPLACE TABLE {table}_sorted AS
            SELECT * FROM {table} ORDER BY donor_id, visit_date;
            
            DROP TABLE {table};
            ALTER TABLE {table}_sorted RENAME TO {table};
        """
        con.execute(sort_query)
        
        print(f"Successfully loaded data into table {table} \n")
    except Exception as e:
        print(f"Fail to full load on table {table} because: {e}")

def load_transformed_donorrate_to_db(con, url, table, batch_size=50000):
    """Load donor rate data in batches"""
    try:
        print(f"Starting to loading data into table {table}")
        
        # Get total row count
        count_query = f"SELECT COUNT(*) as total_rows FROM read_parquet('{url}')"
        result = con.execute(count_query).fetchone()
        total_rows = result[0] if result else 0
        print(f"Total rows to process: {total_rows}")
        
        # Create empty table
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}') LIMIT 0")
        
        # Load in batches
        for offset in range(0, total_rows, batch_size):
            batch_query = f"""
                INSERT INTO {table} 
                SELECT * FROM read_parquet('{url}') 
                LIMIT {batch_size} OFFSET {offset}
            """
            con.execute(batch_query)
            rows_loaded = min(offset + batch_size, total_rows)
            print(f"  Loaded {rows_loaded}/{total_rows} rows ({rows_loaded/total_rows*100:.1f}%)")
        
        # Add age column after loading
        print("Calculating ages...")
        con.execute(f"""
            ALTER TABLE {table} ADD COLUMN age INTEGER;
            UPDATE {table} SET age = year(latest) - birth_date;
        """)
        
        print(f"Successfully loaded data into table {table} \n")
    except Exception as e:
        print(f"Fail to full load on table {table} because: {e}")

def load_population_table(con, url, table):
    try:
        query = f"""CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{url}')"""
        print(f"Starting to loading data into table {table}")
        con.execute(query)
        print(f"Successfully loaded data into table {table} \n")
    except Exception as e:
        print(f"Fail to full load on table {table} because: {e}")

def main():
    try:
        # Create temp directory if it doesn't exist
        temp_dir = "./duck_temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        print(f"Connecting to {db_path}")
        con = duckdb.connect(db_path, config=config)
        
        # Set pragmas after connection
        con.execute("PRAGMA max_temp_directory_size='2GB'")
        con.execute("PRAGMA temp_directory='./duck_temp'")
        con.execute("PRAGMA memory_limit='256MB'")
        con.execute("PRAGMA threads=1")
        con.execute("PRAGMA preserve_insertion_order=false")
        
        print(f"Successfully connected to {db_path}\n")
        
        # Load smaller tables first
        add_table(con, 'inst_code.csv', 'inst_code')
        add_table(con, 'race.csv', 'race')
        load_population_table(con, population_url, 'population')
        
        # Load the problematic historical table with batch processing
        # Adjust batch_size based on your available memory
        load_transformed_historical_to_db(con, historical_url, 'historical', batch_size=30000)
        
        # Load other tables
        load_transformed_retention_to_db(con, retention_url, 'retention', batch_size=50000)
        load_transformed_donorrate_to_db(con, donnorrate_url, "donorrate", batch_size=50000)
        
        # Load spatial data
        print("Adding Malaysia_states table")
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("""
            CREATE or replace TABLE malaysia_states AS 
            SELECT * FROM ST_Read('https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/MYS/ADM1/geoBoundaries-MYS-ADM1_simplified.geojson')
        """)
        print("Successfully added Malaysia_states table\n")
        
        print("Successfully loaded all data to each tables")
        
        
        con.close()
        print("\nDatabase closed successfully")
        
    except Exception as e:
        print(f"Fail because: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()