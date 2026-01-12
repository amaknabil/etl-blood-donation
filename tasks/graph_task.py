import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns
from prefect import task, get_run_logger
from datetime import timedelta
import io
import duckdb
import matplotlib.dates as mdates


def _save_fig_to_buffer(fig) -> io.BytesIO:
    """Saves a matplotlib figure to an in-memory buffer."""
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0) # Rewind the buffer to the beginning so it can be read
        return buf
    finally:
        plt.close(fig) # Explicitly close to prevent memory leaks in long-running flows

@task
def generate_heatmap_retention(rate_retention:dict) -> io.BytesIO:
    logger = get_run_logger() # Initialize logger if using Prefect 2.x
    
    try:
        matrix_data = []
        rows = []

        # 1. Process Data
        for start_year, data in rate_retention.items():
            rows.append(start_year)
            base_count = data['total']
            
            row_dict = {}
            row_dict[0] = 100.0
            
            for future_year, count in data.items():
                if future_year == 'total':
                    continue
                
                delta_years = future_year - start_year
                if delta_years > 0:
                    percentage = (count / base_count) * 100
                    row_dict[delta_years] = percentage
                    
            matrix_data.append(row_dict)

        df = pd.DataFrame(matrix_data, index=rows)
        df = df.sort_index()

        # 2. Create Figure (Assign to 'fig' variable)
        fig = plt.figure(figsize=(12, 8))
        
        # 3. Plot Heatmap
        ax = sns.heatmap(df, 
                        annot=True, 
                        fmt=".1f", 
                        cmap="Reds", 
                        cbar=False, 
                        vmin=0, vmax=100) 

        # 4. Styling
        ax.set_title("% of Donors Still Donating after N Years", fontsize=16, pad=40)
        ax.set_ylabel("Donated Blood in", fontsize=14, labelpad=20)
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position('top') 
        plt.yticks(rotation=0) 
        plt.tight_layout()

        return _save_fig_to_buffer(fig)

    except Exception as e:
        logger.error(f"Failed to build heatmap: {e}")
        raise e
 
@task
def calculate_retention(db_path, table,total_donation) -> dict:
    logger = get_run_logger()
    logger.info(f"Starting to calculate rate of retention")
    con = None
    try:
        con = duckdb.connect(db_path)
        results = {}
        min_year, max_year = con.execute(f"select min(year(visit_date)) ,max(year(visit_date)) from {table}").fetchall()[0]

        for start_year in range(min_year, max_year + 1):
            results[start_year] = {}
            parent_query = f"""
                SELECT COUNT(DISTINCT donor_id) 
                FROM {table}
                WHERE YEAR(visit_date) = {start_year}
                HAVING COUNT(*) >= {total_donation}

            """
            parent_count = con.execute(parent_query).fetchone()[0]

            results[start_year]["total"] = parent_count

            for next_year in range(start_year + 1, max_year + 1):
                query = f"""SELECT 
                            COUNT(DISTINCT r.donor_id)
                            FROM 
                                {table} r
                            WHERE 
                                YEAR(r.visit_date) = {next_year}
                                AND r.donor_id IN (
                                    SELECT donor_id
                                    FROM {table}
                                    WHERE YEAR(visit_date) = {start_year}
                                    GROUP BY donor_id
                                    HAVING COUNT(*) >= {total_donation}
                                );

                """
                count = con.execute(query).fetchone()[0]
                results[start_year][next_year] = count

        return results

    except Exception as e:
        logger.error(f"Fail to calculate retention: {e}")
        raise e
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")

# @task
# def generate_blood_group_line_graph(db_path, table:str) -> io.BytesIO:
#     logger = get_run_logger()
#     con = None
#     try:
#         con = duckdb.connect(db_path)
#         # 1. Get Date Range
#         latest_date_query = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()
#         max_date = pd.to_datetime(latest_date_query[0])
#         start_date = max_date - timedelta(days=29)

#         # 2. Get Data
#         df = pd.read_sql(f"""
#             SELECT visit_date, blood_group, COUNT(*) as total_donations
#             FROM {table}
#             WHERE visit_date >= '{start_date.strftime('%Y-%m-%d')}'
#             AND visit_date <= '{max_date.strftime('%Y-%m-%d')}'
#             AND blood_group NOT IN ('N','U')
#             GROUP BY visit_date, blood_group
#             ORDER BY visit_date
#         """, con)
#         df['visit_date'] = pd.to_datetime(df['visit_date'])

#         # 3. Plot
#         fig, ax = plt.subplots(figsize=(12, 6))
#         sns.lineplot(
#             data=df, x='visit_date', y='total_donations', hue='blood_group', 
#             marker='o', palette='tab10', linewidth=2, ax=ax
#         )

#         ax.set_title(f'Total Daily Donations by Blood Group (Last 30 Days)', fontsize=16)
#         ax.set_xlabel('Date', fontsize=12)
#         ax.set_ylabel('Donations', fontsize=12)
#         ax.legend(title='Blood Group', bbox_to_anchor=(1.05, 1), loc='upper left')
#         ax.grid(True, linestyle='--', alpha=0.6)
#         plt.xticks(rotation=45)
#         plt.tight_layout()

#         return _save_fig_to_buffer(fig)

#     except Exception as e:
#         logger.error(f"Failed to generate blood group graph: {e}")
#         raise e
#     finally:
#         if con:
#             con.close()
#             logger.info("Database connection closed.")

@task
def generate_blood_group_area_graph(db_path, table:str) -> io.BytesIO:
    logger = get_run_logger()
    con = None
    try:
        con = duckdb.connect(db_path)
        
        # 1. Get Date Range
        latest_date_query = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()
        max_date = pd.to_datetime(latest_date_query[0])
        start_date = max_date - timedelta(days=29)

        # 2. Get Data
        df = con.execute(f"""
            SELECT visit_date, blood_group, COUNT(*) as total_donations
            FROM {table}
            WHERE visit_date >= '{start_date.strftime('%Y-%m-%d')}'
            AND visit_date <= '{max_date.strftime('%Y-%m-%d')}'
            AND blood_group NOT IN ('N','U')
            GROUP BY visit_date, blood_group
            ORDER BY visit_date
        """).df()
        df['visit_date'] = pd.to_datetime(df['visit_date'])

        # 3. Pivot Data
        df_pivot = df.pivot(index='visit_date', columns='blood_group', values='total_donations').fillna(0)

        # 4. Plotting
        fig, ax = plt.subplots(figsize=(12, 6))

        df_pivot.plot(
            kind='area', 
            stacked=True, 
            ax=ax, 
            alpha=0.7, 
            colormap='tab10',
            x_compat=True 
        )

        # --- KEY FIXES FOR GAP REMOVAL ---
        # 1. Force the X-axis to start exactly at start_date and end at max_date
        # This removes the whitespace gap on the left and right.
        ax.set_xlim(start_date, max_date)
        
        # 2. Ensure Y-axis starts exactly at 0 (prevents floating look)
        ax.set_ylim(bottom=0)
        # ---------------------------------

        # Formatting
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate(rotation=45, ha='right')


        start_str = start_date.strftime('%d %b %Y')
        end_str = max_date.strftime('%d %b %Y')
        ax.set_title(
            f"Daily Blood Donations by Group (Last 30 Days)\n{start_str} – {end_str}", 
            fontsize=16, 
            pad=20  
        )
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Donations', fontsize=12)
        ax.legend(title='Blood Group', bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()

        return _save_fig_to_buffer(fig)

    except Exception as e:
        logger.error(f"Failed to generate blood group graph: {e}")
        raise e
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")

@task
def generate_age_histogram(db_path, table) -> io.BytesIO:
    """Generates a histogram of donor ages."""
    logger = get_run_logger()
    logger.info("Generating histogram")
    con = None
    try:
        con = duckdb.connect(db_path)
        # Note: In a real production system, try to pass the dataframe 
        # instead of querying SQL again if possible.
        donorrate = con.execute(f"SELECT age FROM {table}").df()
        
        sns.set_style("whitegrid")
        fig, ax = plt.subplots(figsize=(8, 6))

        sns.histplot(
            data=donorrate, x='age', kde=True, bins=20, 
            color='#e74c3c', edgecolor='black', ax=ax
        )
        ax.set_title('Donor Age Distribution', fontsize=14, fontweight='bold')
        ax.set_xlabel('Age', fontsize=12)
        ax.set_ylabel('Count of Donors', fontsize=12)

        return _save_fig_to_buffer(fig)

    except Exception as e:
        logger.error(f"Failed to generate age histogram: {e}")
        raise e
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")

@task
def generate_age_gender_boxplot(db_path, table) -> io.BytesIO:
    """Generates a boxplot of age by gender."""
    logger = get_run_logger()
    con = None
    try:
        con = duckdb.connect(db_path)
        donorrate = con.execute(f"SELECT age, gender FROM {table}").df()
        
        sns.set_style("whitegrid")
        fig, ax = plt.subplots(figsize=(8, 6))

        sns.boxplot(
            data=donorrate, x='gender', y='age', palette='Set2', ax=ax
        )
        ax.set_title('Age Distribution by Gender', fontsize=14, fontweight='bold')
        ax.set_xlabel('Gender', fontsize=12)
        ax.set_ylabel('Age', fontsize=12)

        return _save_fig_to_buffer(fig)

    except Exception as e:
        logger.error(f"Failed to generate age boxplot: {e}")
        raise e
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")