import csv
import logging
from .db_operations import resource_path

def import_csv_to_table(cursor, csv_filename, table_name):
    csv_path = resource_path(csv_filename)
    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=';')
            next(csvreader)  # Skip header
            for row in csvreader:
                if row and not row[0].startswith('#'):
                    placeholders = ','.join(['?' for _ in row])
                    cursor.execute(f"INSERT OR REPLACE INTO {table_name} VALUES ({placeholders})", row)
        logging.info(f"Data from {csv_filename} imported into {table_name} table")
    except FileNotFoundError:
        logging.error(f"CSV file not found: {csv_path}")
    except Exception as e:
        logging.error(f"Error importing data from {csv_filename}: {e}")
        logging.error(f"Problematic row: {row}")