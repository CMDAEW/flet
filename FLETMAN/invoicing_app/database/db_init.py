import logging
import sqlite3
import csv
import os
from .db_operations import get_db_connection, resource_path

def initialize_database():
    logging.info("Starte Datenbankinitialisierung...")
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
        fill_table_from_csv(cursor, 'price_list', 'EP.csv')
        fill_table_from_csv(cursor, 'Materialpreise', 'Materialpreise.CSV')
        fill_table_from_csv(cursor, 'Formteile', 'Formteile.csv')
        fill_table_from_csv(cursor, 'Taetigkeiten', 'Taetigkeiten.csv')
        
        conn.commit()
        logging.info("Datenbankinitialisierung erfolgreich abgeschlossen.")
    except Exception as e:
        logging.error(f"Fehler bei der Datenbankinitialisierung: {e}")
        conn.rollback()
    finally:
        conn.close()

def fill_table_from_csv(cursor, table_name, csv_filename):
    csv_path = resource_path(csv_filename)
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=';')
        next(csvreader)  # Skip header
        for row in csvreader:
            if row and not row[0].startswith('#'):
                insert_row_into_table(cursor, table_name, row)

def insert_row_into_table(cursor, table_name, row):
    # Implement the logic to insert rows into specific tables
    pass