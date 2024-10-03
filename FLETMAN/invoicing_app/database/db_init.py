import logging
import sqlite3
import csv
import os
from .db_operations import get_db_connection, resource_path, get_db_path

def initialize_database():
    logging.info("Starte Datenbankinitialisierung...")
    logging.info(f"Current working directory: {os.getcwd()}")
    logging.info(f"Database path: {get_db_path}")
    logging.info(f"Resource path for EP.csv: {resource_path('EP.csv')}")
    logging.info(f"Resource path for Materialpreise.CSV: {resource_path('Materialpreise.CSV')}")
    logging.info(f"Resource path for Formteile.csv: {resource_path('Formteile.csv')}")
    logging.info(f"Resource path for Taetigkeiten.csv: {resource_path('Taetigkeiten.csv')}")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_list (
                id INTEGER PRIMARY KEY,
                item_number TEXT NOT NULL,
                dn REAL,
                da REAL,
                size TEXT,
                value REAL,
                unit TEXT,
                bauteil TEXT
            )
        ''')
        
        # Add other table creation statements here
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY,
                client_name TEXT NOT NULL,
                bestell_nr TEXT,
                bestelldatum TEXT,
                baustelle TEXT,
                anlagenteil TEXT,
                aufmass_nr TEXT,
                aufmassart TEXT,
                auftrags_nr TEXT,
                ausfuehrungsbeginn TEXT,
                ausfuehrungsende TEXT,
                total REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY,
                invoice_id INTEGER,
                item_description TEXT,
                dn REAL,
                da REAL,
                size TEXT,
                item_price REAL,
                quantity INTEGER,
                taetigkeit TEXT,
                FOREIGN KEY (invoice_id) REFERENCES invoices (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Formteile (
                Position INTEGER PRIMARY KEY,
                Formteilbezeichnung TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Taetigkeiten (
                Position INTEGER PRIMARY KEY,
                Taetigkeit TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Zuschlaege (
                Position INTEGER PRIMARY KEY,
                Zuschlag TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Materialpreise (
                RV_Pos INTEGER PRIMARY KEY,
                Benennung TEXT NOT NULL,
                Material TEXT,
                Abmessung_ME TEXT,
                EP REAL,
                per TEXT
            )
        ''')

        # Add other table creation statements and data import logic here
        
        # Fill tables with initial data
        fill_table_from_csv(cursor, 'price_list', 'EP.csv', force_refill=True)
        fill_table_from_csv(cursor, 'Materialpreise', 'Materialpreise.CSV', force_refill=True)
        fill_table_from_csv(cursor, 'Formteile', 'Formteile.csv', force_refill=True)
        fill_table_from_csv(cursor, 'Taetigkeiten', 'Taetigkeiten.csv', force_refill=True)
        
        conn.commit()
        logging.info("Datenbankinitialisierung erfolgreich abgeschlossen.")
    except Exception as e:
        logging.error(f"Fehler bei der Datenbankinitialisierung: {e}")
        conn.rollback()
    finally:
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
                INSERT INTO price_list (id, item_number, dn, da, size, value, unit, bauteil)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(row[0]),
                row[1],
                float(row[2]) if row[2] else None,
                float(row[3]) if row[3] else None,
                row[4],
                float(row[5].replace(',', '.')) if row[5] else None,
                row[6],
                row[7]
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into price_list: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Materialpreise':
        try:
            cursor.execute('''
                INSERT INTO Materialpreise (RV_Pos, Benennung, Material, Abmessung_ME, EP, per)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                int(row[0]),
                row[1],
                row[2] if row[2] != '' else None,
                f"{row[3]} {row[4]}".strip(),
                float(row[5].replace(',', '.')),
                row[6]
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into Materialpreise: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Formteile':
        try:
            cursor.execute('''
                INSERT INTO Formteile (Position, Formteilbezeichnung, Faktor)
                VALUES (?, ?, ?)
            ''', (
                int(row[0]),
                row[1],
                float(row[2].replace(',', '.'))
            ))
        except ValueError as e:
            logging.error(f"Error inserting row into Formteile: {e}")
            logging.error(f"Problematic row: {row}")
    elif table_name == 'Taetigkeiten':
        try:
            cursor.execute('''
                INSERT INTO Taetigkeiten (Position, Taetigkeit, Faktor)
                VALUES (?, ?, ?)
            ''', (
                int(row[0]),
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