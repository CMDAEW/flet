import logging
import sqlite3
import csv
import os
from .db_operations import get_db_connection, resource_path, get_db_path
from .csv_import import import_csv_to_table

def initialize_database():
    logging.info("Starting database initialization...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create invoice table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoice (
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER,
        client_name TEXT NOT NULL,
        bestell_nr TEXT,
        bestelldatum TEXT,
        baustelle TEXT,
        anlagenteil TEXT,
        aufmass_nr TEXT,
        auftrags_nr TEXT,
        ausfuehrungsbeginn TEXT,
        ausfuehrungsende TEXT,
        total_amount REAL
    )
    ''')

    # Create invoice_items table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY,
        invoice_id INTEGER,
        Positionsnummer TEXT,
        DN REAL,
        DA REAL,
        Size TEXT,
        Value REAL,
        Unit TEXT,
        Bauteil TEXT,
        quantity INTEGER,
        zwischensumme REAL,
        taetigkeit TEXT,
        FOREIGN KEY (invoice_id) REFERENCES invoice (id),
        FOREIGN KEY (Positionsnummer) REFERENCES price_list (Positionsnummer)
    )
    ''')

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_list (
            Positionsnummer TEXT PRIMARY KEY,
            DN REAL,
            DA REAL,
            Size TEXT,
            Value REAL,
            Unit TEXT,
            Bauteil TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Taetigkeiten (
            Positionsnummer TEXT PRIMARY KEY,
            Taetigkeit TEXT NOT NULL,
            Faktor REAL NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Materialpreise (
            Positionsnummer TEXT PRIMARY KEY,
            Benennung TEXT NOT NULL,
            Material TEXT,
            Abmessung TEXT,
            ME TEXT,
            EP REAL,
            per TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Zuschlaege (
            Positionsnummer TEXT PRIMARY KEY,
            Zuschlag TEXT NOT NULL,
            Faktor REAL NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Formteile (
            Positionsnummer TEXT PRIMARY KEY,
            Formteilbezeichnung TEXT NOT NULL,
            Faktor REAL NOT NULL
        )
    ''')

    # Import data from CSV files
    import_csv_to_table(cursor, 'EP.csv', 'price_list')
    import_csv_to_table(cursor, 'Taetigkeiten.csv', 'Taetigkeiten')
    import_csv_to_table(cursor, 'Materialpreise.csv', 'Materialpreise')
    import_csv_to_table(cursor, 'Zuschlaege.csv', 'Zuschlaege')
    import_csv_to_table(cursor, 'Formteile.csv', 'Formteile')

    conn.commit()
    logging.info("Database initialization completed successfully")
    conn.close()

def fill_table_from_csv(cursor, table_name, csv_filename, force_refill=False):
    csv_path = resource_path(csv_filename)
    try:
        if force_refill:
            cursor.execute(f"DELETE FROM {table_name}")
        
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        if cursor.fetchone()[0] == 0 or force_refill:
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                csvreader = csv.reader(csvfile, delimiter=';')
                next(csvreader)  # Skip header
                for row in csvreader:
                    if row and not row[0].startswith('#'):
                        insert_row_into_table(cursor, table_name, row)
            logging.info(f"Table {table_name} filled with data from {csv_filename}")
        else:
            logging.info(f"Table {table_name} already contains data. Skipping import.")
    except FileNotFoundError:
        logging.error(f"CSV file not found: {csv_path}")
    except Exception as e:
        logging.error(f"Error processing CSV file {csv_filename}: {e}")

def insert_row_into_table(cursor, table_name, row):
    if table_name == 'price_list':
        try:
            cursor.execute('''
                INSERT INTO price_list (item_number, dn, da, size, value, unit, bauteil)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                row[0],
                float(row[1]) if row[1] else None,
                float(row[2]) if row[2] else None,
                row[3],
                float(row[4].replace(',', '.')) if row[4] else None,
                row[5],
                row[6]
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into price_list: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Materialpreise':
        try:
            cursor.execute('''
                INSERT INTO Materialpreise (Positionsnummer, Benennung, Material, Abmessung, ME, EP, per)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                row[0],
                row[1],
                row[2] if row[2] != '' else None,
                row[3],
                row[4],
                float(row[5].replace(',', '.')),
                row[6]
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into Materialpreise: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Formteile':
        try:
            cursor.execute('''
                INSERT INTO Formteile (Positionsnummer, Formteilbezeichnung, Preis)
                VALUES (?, ?, ?)
            ''', (
                row[0],
                row[1],
                float(row[2].replace(',', '.'))
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into Formteile: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Taetigkeiten':
        try:
            cursor.execute('''
                INSERT INTO Taetigkeiten (Positionsnummer, Taetigkeit, Faktor)
                VALUES (?, ?, ?)
            ''', (
                row[0],
                row[1],
                float(row[2].replace(',', '.'))
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into Taetigkeiten: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Zuschlaege':
        try:
            cursor.execute('''
                INSERT INTO Zuschlaege (Position, Zuschlag, Faktor)
                VALUES (?, ?, ?)
            ''', (
                int(row[0]),
                row[1],
                float(row[2].replace(',', '.'))
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into Zuschlaege: {e}")
            logging.error(f"Problematic row: {row}")
    else:
        logging.error(f"Unknown table name: {table_name}")