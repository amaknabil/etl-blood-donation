
import duckdb
from datetime import datetime

def check_available_other_data(url: str, db_path: str, table: str):

    con = None

    try:
        con = duckdb.connect(db_path)
        count_before = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        query_remote = f"SELECT COUNT(*) FROM read_parquet('{url}')"
        count_after = con.execute(query_remote).fetchone()[0]

        print(f"Local count: {count_before} | Remote count: {count_after}")

        if count_after > count_before:
            print("New data detected. Proceeding...")
            return True
        else:
            print(
                f"No new rows found. Remote ({count_after}) is not greater "
                f"than Local ({count_before}) at {datetime.now()}."
            )
    except Exception as e:
        print(f"Data verification failed: {e}")
    finally:
        if con:
            con.close()


check_available_other_data("https://data.kijang.net/dea/donorrate/data.parquet","blood_data.duckdb","donorrate")