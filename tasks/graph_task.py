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

    buf = io.BytesIO()
    try:
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0) 
        return buf
    finally:
        plt.close(fig) 

@task
def generate_heatmap_retention(rate_retention:dict) -> io.BytesIO:
    logger = get_run_logger() 
    
    try:
        matrix_data = []
        rows = []

  
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


        fig = plt.figure(figsize=(12, 8))
        ax = sns.heatmap(df, 
                        annot=True, 
                        fmt=".0f", 
                        cmap="Reds", 
                        cbar=False, 
                        vmin=0, vmax=50) 

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

@task
def generate_donor_heatmap_demographic(db_path):
    con = None
    try:
        # --- 1. Fetch Data ---
        con = duckdb.connect(db_path)
    
        # Using the Unified CTE Query (Population + Donors)
        query = """
            WITH pop_stats AS (
            SELECT 
                sex as gender,
                -- Rename the transformed column to avoid ambiguity with source column
                CASE
                    WHEN age = '15-19' THEN '18-19'
                    ELSE age
                END as age_group, 
                CASE 
                    WHEN ethnicity = 'bumi_malay' THEN 'Malay'
                    WHEN ethnicity = 'chinese' THEN 'Chinese'
                    WHEN ethnicity = 'indian' THEN 'Indian'
                    WHEN ethnicity = 'other_noncitizen' THEN 'Foreigner'
                    ELSE 'Lain-lain'
                END AS race,
                SUM(
                    CASE
                        WHEN age = '15-19' THEN (population * 0.4)
                        ELSE population
                    END
                    ) * 1000 as total_population
            FROM main.population p 
            WHERE YEAR(date) = 2025
            AND age NOT IN ('0-4','5-9','10-14','65-69','70-74','75-79','80-84','85+','overall')
            AND sex IN ('male', 'female')
            GROUP BY 1, 2, 3
        ),

        donor_stats AS (
            SELECT 
                gender, 
                age as age_group, 
                race, 
                COUNT(*) AS total_donations
            FROM (
                SELECT 
                    CASE 
                        WHEN d.gender = 'F' THEN 'female'
                        WHEN d.gender = 'M' THEN 'male'
                    END as gender, 
                    CASE 
                        WHEN r.race = 'chinese' THEN 'Chinese'
                        WHEN r.race = 'indian' THEN 'Indian'
                        WHEN r.race = 'malay' THEN 'Malay'
                        WHEN r.race = 'foreigner' THEN 'Foreigner'
                        ELSE 'Lain-lain' 
                    END AS race,
                    CASE 
                        WHEN d.age BETWEEN 18 AND 19 THEN '18-19'
                        WHEN d.age BETWEEN 20 AND 24 THEN '20-24'
                        WHEN d.age BETWEEN 25 AND 29 THEN '25-29'
                        WHEN d.age BETWEEN 30 AND 34 THEN '30-34'
                        WHEN d.age BETWEEN 35 AND 39 THEN '35-39'
                        WHEN d.age BETWEEN 40 AND 44 THEN '40-44'
                        WHEN d.age BETWEEN 45 AND 49 THEN '45-49'
                        WHEN d.age BETWEEN 50 AND 54 THEN '50-54'
                        WHEN d.age BETWEEN 55 AND 59 THEN '55-59'
                        WHEN d.age BETWEEN 60 AND 64 THEN '60-64'
                    END AS age
                FROM main.donorrate d 
                LEFT JOIN main.race r ON d.race = r.race_code
                WHERE d.latest BETWEEN '2025-01-06' AND '2026-01-05'
                AND d.age BETWEEN 18 AND 64
            ) AS cleaned_data 
            GROUP BY 1, 2, 3
        )

        SELECT 
            p.gender,
            p.race,
            p.age_group as age,
            (COALESCE(d.total_donations, 0) / NULLIF(p.total_population, 0)::FLOAT) * 100 as donation_rate_pct
        FROM pop_stats p
        LEFT JOIN donor_stats d 
            ON p.gender = d.gender 
            AND p.race = d.race 
            AND p.age_group = d.age_group
        ORDER BY p.gender, p.race, p.age_group;
        """
        
        raw_df = con.execute(query).fetch_df()

        # --- 2. Process Data ---
        
        # Pivot the data from Long format to Wide format for the Heatmap
        # Index: gender, race | Columns: age | Values: donation_rate_pct
        df_pivot = raw_df.pivot_table(
            index=['gender', 'race'], 
            columns='age', 
            values='donation_rate_pct'
        ).reset_index()

        # Define the exact age columns order (matching SQL output format)
        age_cols = ['18-19', '20-24', '25-29', '30-34', '35-39', 
                    '40-44', '45-49', '50-54', '55-59', '60-64']
        
        # Ensure only these columns exist (and in correct order)
        df_pivot = df_pivot[['gender', 'race'] + age_cols]

        # Calculate 'Overall' (Row Mean)
        df_pivot['Overall'] = df_pivot[age_cols].mean(axis=1)

        # Define Custom Race Order for display
        custom_order = ['Chinese', 'Indian', 'Malay', 'Lain-lain', 'Foreigner']

        # Split into Male and Female DataFrames & Format Index
        # Male
        df_m = df_pivot[df_pivot['gender'] == 'male'].set_index('race').reindex(custom_order)
        df_m.index = df_m.index + ' M'  # e.g., "Chinese M"
        
        # Female
        df_f = df_pivot[df_pivot['gender'] == 'female'].set_index('race').reindex(custom_order)
        df_f.index = df_f.index + ' F'  # e.g., "Chinese F"

        # --- 3. Plotting ---
        fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                             gridspec_kw={'height_ratios': [1, 1]})

        fig.suptitle("Malaysia: Blood Donor Participation Rate (%) by Sex, Ethnicity, and Age\n(Donors / Total Population)",
                     fontsize=14, y=0.98)

        def plot_segment(data, ax, is_top=False):
            # 1. Main Heatmap
            # Note: vmin/vmax might need adjustment based on real data ranges (e.g. 0 to 3%)
            sns.heatmap(data[age_cols], annot=True, fmt=".1f", cmap="Greens", vmin=0, vmax=5,
                        cbar=False, ax=ax, linewidths=1, linecolor='white', annot_kws={"size": 11})

            # 2. Inset for Overall 
            ax_ovr = ax.inset_axes([1.02, 0, 0.1, 1])
            sns.heatmap(data[['Overall']], annot=True, fmt=".1f", cmap="Greens", vmin=0, vmax=3,
                        cbar=False, ax=ax_ovr, linewidths=1, linecolor='white', annot_kws={"size": 11})

            # --- CLEANING Y-AXIS (SIDE TITLES) ---
            ax.set_ylabel('') 
            ax.tick_params(axis='y', rotation=0, labelsize=11)
            
            ax_ovr.set_ylabel('') 
            ax_ovr.set_yticks([]) 

            # --- X-AXIS LABELS ---
            if is_top:
                # Move ticks to top
                ax.xaxis.tick_top()
                ax.set_xticklabels(age_cols, rotation=0, fontsize=11)
                
                # Overall column label at top only
                ax_ovr.xaxis.tick_top()
                ax_ovr.set_xticklabels(['Overall'], rotation=0, fontsize=11)
            else:
                # Show age labels at the bottom for bottom plot
                ax.set_xticklabels(age_cols, rotation=0, fontsize=11)
                # Remove Overall label from bottom plot
                ax_ovr.set_xticklabels([])

            # Clear tick marks
            ax.tick_params(left=False, bottom=False, top=False)
            ax_ovr.tick_params(left=False, bottom=False, top=False)

        # Plot Segments
        plot_segment(df_m, ax_top, is_top=True)
        plot_segment(df_f, ax_bot, is_top=False)

        # Enable x-axis ticks at the bottom explicitly
        ax_bot.tick_params(axis='x', bottom=True, top=False, labelbottom=True)
        ax_bot.xaxis.set_tick_params(length=6)

        plt.subplots_adjust(top=0.88, bottom=0.08, left=0.15, right=0.9, hspace=0.2)
        
        return _save_fig_to_buffer(fig)

    except Exception as e:
        print(f"Error generating heatmap: {e}")
        raise e
    finally:
        if con:
            con.close()
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

    con = None
    try:
        # --- 1. Fetch Data ---
        con = duckdb.connect(db_path)
    
        query = """
            WITH pop_stats AS (
            SELECT 
                sex as gender,
                CASE
                    WHEN age = '15-19' THEN '18-19'
                    ELSE age
                END as age_group, 
                CASE 
                    WHEN ethnicity = 'bumi_malay' THEN 'Malay'
                    WHEN ethnicity = 'chinese' THEN 'Chinese'
                    WHEN ethnicity = 'indian' THEN 'Indian'
                    WHEN ethnicity = 'other_noncitizen' THEN 'Foreigner'
                    ELSE 'Lain²'
                END AS race,
                SUM(
                    CASE
                        WHEN age = '15-19' THEN (population * 0.4)
                        ELSE population
                    END
                    ) * 1000 as total_population
            FROM main.population p 
            WHERE YEAR(date) = 2025
            AND age NOT IN ('0-4','5-9','10-14','65-69','70-74','75-79','80-84','85+','overall')
            AND sex IN ('male', 'female')
            GROUP BY 1, 2, 3
        ),

        donor_stats AS (
            SELECT 
                gender, 
                age as age_group, 
                race, 
                COUNT(*) AS total_donations
            FROM (
                SELECT 
                    CASE 
                        WHEN d.gender = 'F' THEN 'female'
                        WHEN d.gender = 'M' THEN 'male'
                    END as gender, 
                    CASE 
                        WHEN r.race = 'chinese' THEN 'Chinese'
                        WHEN r.race = 'indian' THEN 'Indian'
                        WHEN r.race = 'malay' THEN 'Malay'
                        WHEN r.race = 'foreigner' THEN 'Foreigner'
                        ELSE 'Lain²' 
                    END AS race,
                    CASE 
                        WHEN d.age BETWEEN 18 AND 19 THEN '18-19'
                        WHEN d.age BETWEEN 20 AND 24 THEN '20-24'
                        WHEN d.age BETWEEN 25 AND 29 THEN '25-29'
                        WHEN d.age BETWEEN 30 AND 34 THEN '30-34'
                        WHEN d.age BETWEEN 35 AND 39 THEN '35-39'
                        WHEN d.age BETWEEN 40 AND 44 THEN '40-44'
                        WHEN d.age BETWEEN 45 AND 49 THEN '45-49'
                        WHEN d.age BETWEEN 50 AND 54 THEN '50-54'
                        WHEN d.age BETWEEN 55 AND 59 THEN '55-59'
                        WHEN d.age BETWEEN 60 AND 64 THEN '60-64'
                    END AS age
                FROM main.donorrate d 
                LEFT JOIN main.race r ON d.race = r.race_code
                WHERE d.latest BETWEEN '2025-01-06' AND '2026-01-05'
                AND d.age BETWEEN 18 AND 64
            ) AS cleaned_data 
            GROUP BY 1, 2, 3
        )

        SELECT 
            p.gender,
            p.race,
            p.age_group as age,
            (COALESCE(d.total_donations, 0) / NULLIF(p.total_population, 0)::FLOAT) * 100 as donation_rate_pct
        FROM pop_stats p
        LEFT JOIN donor_stats d 
            ON p.gender = d.gender 
            AND p.race = d.race 
            AND p.age_group = d.age_group
        ORDER BY p.gender, p.race, p.age_group;
        """
        
        raw_df = con.execute(query).fetch_df()

        # --- 2. Process Data ---
        
        df_pivot = raw_df.pivot_table(
            index=['gender', 'race'], 
            columns='age', 
            values='donation_rate_pct'
        ).reset_index()

        age_cols = ['18-19', '20-24', '25-29', '30-34', '35-39', 
                    '40-44', '45-49', '50-54', '55-59', '60-64']
        
        df_pivot = df_pivot[['gender', 'race'] + age_cols]

        # Calculate 'Overall' (Row Mean)
        df_pivot['Overall'] = df_pivot[age_cols].mean(axis=1)

        # Split into Male and Female DataFrames
        df_m = df_pivot[df_pivot['gender'] == 'male'].copy()
        df_f = df_pivot[df_pivot['gender'] == 'female'].copy()

        # SORTING LOGIC: Sort by 'Overall' descending
        df_m = df_m.sort_values(by='Overall', ascending=False)
        df_f = df_f.sort_values(by='Overall', ascending=False)

        # Format Index Labels
        df_m = df_m.set_index('race')
        df_m.index = df_m.index + ' M'  
        
        df_f = df_f.set_index('race')
        df_f.index = df_f.index + ' F'

        # --- 3. Plotting ---
        fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                             gridspec_kw={'height_ratios': [len(df_m), len(df_f)]})

        fig.suptitle("Malaysia: Blood Donor Rates by Sex, Ethnicity, and Age\n(using unique donors from 06 Jan 2025 to 05 Jan 2026)",
                     fontsize=14, y=0.96)

        def plot_segment(data, ax, is_top=False):
            # 1. Main Heatmap
            sns.heatmap(data[age_cols], annot=True, fmt=".1f", cmap="Greens", vmin=0, vmax=5,
                        cbar=False, ax=ax, linewidths=1, linecolor='white', annot_kws={"size": 11})

            # 2. Inset for Overall 
            ax_ovr = ax.inset_axes([1.02, 0, 0.1, 1])
            
            # --- FIX IS HERE: changed ax_ovr=ax_ovr to ax=ax_ovr ---
            sns.heatmap(data[['Overall']], annot=True, fmt=".1f", cmap="Greens", vmin=0, vmax=3,
                        cbar=False, ax=ax_ovr, linewidths=1, linecolor='white', annot_kws={"size": 11})

            # --- CLEANING AXIS ---
            ax.set_ylabel('') 
            ax.set_xlabel('')
            ax.tick_params(axis='y', rotation=0, labelsize=11)
            
            ax_ovr.set_ylabel('') 
            ax_ovr.set_xlabel('')
            ax_ovr.set_yticks([]) 

            # --- X-AXIS LABELS LOGIC ---
            if is_top:
                # Labels ONLY at the top of the top chart
                ax.xaxis.tick_top()
                ax.set_xticklabels(age_cols, rotation=0, fontsize=11)
                
                ax_ovr.xaxis.tick_top()
                ax_ovr.set_xticklabels(['Overall'], rotation=0, fontsize=11)
            else:
                # NO labels for the bottom chart
                ax.set_xticklabels([])
                ax_ovr.set_xticklabels([])
                ax.tick_params(bottom=False) 
                ax_ovr.tick_params(bottom=False)

            # Clear tick marks everywhere
            ax.tick_params(left=False, top=False)
            ax_ovr.tick_params(left=False, top=False)

        # Plot Segments
        plot_segment(df_m, ax_top, is_top=True)
        plot_segment(df_f, ax_bot, is_top=False)

        # Adjust layout
        plt.subplots_adjust(top=0.85, bottom=0.05, left=0.15, right=0.9, hspace=0.3)
        
        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"Error generating heatmap: {e}")
        raise e
    finally:
        if con:
            con.close()