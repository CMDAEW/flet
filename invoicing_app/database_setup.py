import sqlite3
import csv
import os
import sys
import appdirs
import shutil
import logging

_temp_db_file = None

import tempfile
import shutil

def get_db_connection():
    db_path = get_db_path()
    return sqlite3.connect(db_path)

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        # Wir sind in einer PyInstaller-Bundle
        base_path = sys._MEIPASS
    else:
        # Wir sind in einem normalen Python-Prozess
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_db_path():
    app_dir = appdirs.user_data_dir("InvoicingApp", "KAEFER Industrie GmbH")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return os.path.join(app_dir, 'invoicing.db')

def cleanup_temp_db():
    global _temp_db_file
    if _temp_db_file:
        _temp_db_file.close()
        os.unlink(_temp_db_file.name)

def initialize_database():
    logging.info("Starte Datenbankinitialisierung...")
    db_path = get_db_path()
    logging.info(f"Datenbankpfad: {db_path}")
    
    if not os.path.exists(db_path):
        logging.info("Datenbank existiert nicht. Erstelle neue Datenbank.")
        initial_db_path = resource_path('invoicing.db')
        shutil.copy2(initial_db_path, db_path)
        logging.info(f"Initiale Datenbank kopiert nach: {db_path}")
    else:
        logging.info("Datenbank existiert bereits.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Erstelle price_list Tabelle
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
        logging.info("price_list Tabelle erfolgreich erstellt oder existiert bereits.")
        
        # Erstelle invoices Tabelle
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY,
                client_name TEXT NOT NULL,
                client_email TEXT,
                invoice_date TEXT,
                total REAL
            )
        ''')
        logging.info("invoices Tabelle erfolgreich erstellt oder existiert bereits.")
        
        # Erstelle invoice_items Tabellew
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
                FOREIGN KEY (invoice_id) REFERENCES invoices (id)
            )
        ''')
        logging.info("invoice_items Tabelle erfolgreich erstellt oder existiert bereits.")
        
        # Fülle price_list Tabelle, wenn sie leer ist
        cursor.execute("SELECT COUNT(*) FROM price_list")
        if cursor.fetchone()[0] == 0:
            logging.info("price_list ist leer. Fülle mit Daten aus CSV...")
            csv_path = resource_path('EP_SWF.csv')
            with open(csv_path, 'r') as csvfile:
                csvreader = csv.reader(csvfile)
                next(csvreader)  # Überspringe die Kopfzeile
                for row in csvreader:
                    if row and not row[0].startswith('#'):  # Ignoriere leere Zeilen und Kommentare
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
                                float(row[5]) if row[5] else None,
                                row[6],
                                row[7]
                            ))
                        except Exception as e:
                            logging.error(f"Fehler beim Einfügen der Zeile {row}: {e}")
            logging.info("Daten erfolgreich in price_list eingefügt.")
        
        conn.commit()
        logging.info("Datenbankinitialisierung erfolgreich abgeschlossen.")
    except Exception as e:
        logging.error(f"Fehler bei der Datenbankinitialisierung: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_unique_bauteil_values():
    db_path = get_db_path()
    print(f"Versuche, Datenbank zu öffnen: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT bauteil FROM price_list ORDER BY bauteil')
        bauteil_values = [row[0] for row in cursor.fetchall()]
        conn.close()
        return bauteil_values
    except sqlite3.Error as e:
        print(f"Fehler beim Abrufen der Bauteil-Werte: {e}")
        print(f"Tabellen in der Datenbank:")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(f"- {table[0]}")
        conn.close()
        return []

def get_unique_dn_da_pairs():
    logging.info("Versuche, eindeutige DN/DA-Paare abzurufen...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logging.info(f"Vorhandene Tabellen: {tables}")
        
        cursor.execute('SELECT DISTINCT DN, DA FROM price_list ORDER BY DN, DA')
        dn_da_pairs = cursor.fetchall()
        logging.info(f"Gefundene DN/DA-Paare: {dn_da_pairs}")
        return dn_da_pairs
    except sqlite3.Error as e:
        logging.error(f"Fehler beim Abrufen der DN/DA-Paare: {e}")
        return []
    finally:
        conn.close()

def get_unique_customer_names():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT customer_name FROM invoices ORDER BY customer_name')
    names = [row[0] for row in cursor.fetchall()]
    conn.close()
    return names

def check_database_structure():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Vorhandene Tabellen:", tables)
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table[0]});")
        columns = cursor.fetchall()
        print(f"Spalten in {table[0]}:", columns)
    
    conn.close()

if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
