import duckdb


con = duckdb.connect("blood_data.duckdb")

duckdb.read_csv("inst_code.csv").show()
