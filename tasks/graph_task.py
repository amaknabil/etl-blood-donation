import pandas as pd
import numpy as np
import matplotlib
# CRITICAL: Use 'Agg' backend to prevent "display not found" errors on servers
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns
from prefect import task, get_run_logger
from datetime import timedelta
import io
import duckdb

# --- Helper Function to D.R.Y (Don't Repeat Yourself) ---
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
def calculate_retention(db_path, table) -> dict:
    logger = get_run_logger()
    logger.info(f"Starting to calculate rate of retention")
    con = None
    try:
        con = duckdb.connect(db_path)
        # 1. Get Date Range
        year_range = con.execute(f"SELECT min(year(visit_date)), max(year(visit_date)) FROM {table}").fetchall()
        start_year, end_year = year_range[0][0], year_range[0][1]

        # 2. Get Total New Donors (Denominator)
        total_donors_query = con.execute(f"""
            SELECT year(visit_date) as year, count(distinct donor_id)
            FROM {table} 
            WHERE visit_status = 'First Visit'
            GROUP BY year
        """).fetchall()
        total_new_donor = dict(total_donors_query)

        # 3. Calculate Retention (Numerator)
        rate_retention = {}

        for i in range(0, end_year - start_year + 1):
            parent_year = start_year + i
            
            if parent_year not in total_new_donor or total_new_donor[parent_year] == 0:
                continue
                
            rate_retention[parent_year] = {}
            
            for j in range(0, end_year - parent_year + 1):
                child_year = parent_year + j
                
                # Optimized Self-Join Query
                numerator = con.execute(f"""
                    SELECT count(distinct t2.donor_id)
                    FROM {table} t1
                    JOIN {table} t2 ON t1.donor_id = t2.donor_id
                    WHERE t1.visit_status = 'First Visit'
                    AND year(t1.visit_date) = {parent_year} 
                    AND year(t2.visit_date) = {child_year}
                """).fetchone()[0]
                
                if total_new_donor[parent_year] > 0:
                    rate = (numerator / total_new_donor[parent_year]) * 100
                    rate_retention[parent_year][child_year] = round(rate, 2)
                    
        return rate_retention

    except Exception as e:
        logger.error(f"Fail to calculate retention: {e}")
        raise e
    finally:
        if con:
            con.close()
            logger.info("Database connection closed.")


@task
def generate_heatmap_retention(rate_retention: dict) -> io.BytesIO:
    logger = get_run_logger()
    try:
        # Data Prep
        data = rate_retention 
        rows = sorted(data.keys()) 
        cols = sorted({child for inner in data.values() for child in inner.keys()})
        mat = pd.DataFrame(index=rows, columns=cols, dtype=float)

        for parent, children in data.items():
            for child, val in children.items():
                mat.loc[parent, child] = val

        mat_for_plot = mat.T.sort_index().sort_index(axis=1)

        # Plotting
        fig, ax = plt.subplots(figsize=(12, 8))
        masked = np.ma.masked_invalid(mat_for_plot.values)
        cmap = plt.cm.Reds
        cmap.set_bad(color='#f5f5f5')

        im = ax.imshow(masked, aspect='auto', cmap=cmap, interpolation='nearest')

        # Axis Config
        ax.set_xticks(range(len(mat_for_plot.columns)))
        ax.set_xticklabels(mat_for_plot.columns, rotation=45, ha='right')
        ax.set_yticks(range(len(mat_for_plot.index)))
        ax.set_yticklabels(mat_for_plot.index)
        ax.set_xlabel('Cohort Year (First Visit)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Retention Year (Return Visit)', fontsize=12, fontweight='bold')
        ax.set_title('Donor Retention Heatmap (%)', fontsize=14, pad=20)

        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Retention Rate (%)')

        # Annotations
        threshold = masked.max() / 2 
        for i in range(len(mat_for_plot.index)):
            for j in range(len(mat_for_plot.columns)):
                val = mat_for_plot.iat[i, j]
                if not pd.isna(val):
                    text_color = 'white' if val > threshold else 'black'
                    ax.text(j, i, f"{val:.1f}%", va='center', ha='center', 
                            fontsize=8, color=text_color)
        
        plt.tight_layout()
        
        # Return the image buffer
        return _save_fig_to_buffer(fig)

    except Exception as e:
        logger.error(f"Failed to build heatmap: {e}")
        raise e

@task
def generate_blood_group_line_graph(db_path, table:str) -> io.BytesIO:
    logger = get_run_logger()
    con = None
    try:
        con = duckdb.connect(db_path)
        # 1. Get Date Range
        latest_date_query = con.execute(f"SELECT MAX(visit_date) FROM {table}").fetchone()
        max_date = pd.to_datetime(latest_date_query[0])
        start_date = max_date - timedelta(days=29)

        # 2. Get Data
        df = pd.read_sql(f"""
            SELECT visit_date, blood_group, COUNT(*) as total_donations
            FROM {table}
            WHERE visit_date >= '{start_date.strftime('%Y-%m-%d')}'
            AND visit_date <= '{max_date.strftime('%Y-%m-%d')}'
            AND blood_group NOT IN ('N','U')
            GROUP BY visit_date, blood_group
            ORDER BY visit_date
        """, con)
        df['visit_date'] = pd.to_datetime(df['visit_date'])

        # 3. Plot
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.lineplot(
            data=df, x='visit_date', y='total_donations', hue='blood_group', 
            marker='o', palette='tab10', linewidth=2, ax=ax
        )

        ax.set_title(f'Total Daily Donations by Blood Group (Last 30 Days)', fontsize=16)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Donations', fontsize=12)
        ax.legend(title='Blood Group', bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, linestyle='--', alpha=0.6)
        plt.xticks(rotation=45)
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