# -*- coding: utf-8 -*-
from cmath import e
import logging
import flet as ft
import sqlite3
import csv
import os
import sys
import appdirs
import shutil
import tempfile
from datetime import datetime
from httpx import options
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.platypus import Image, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from tomlkit import item

_temp_db_file = None

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.text_factory = str
    return conn

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
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
        
        # Create Formteile table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Formteile (
                Position INTEGER PRIMARY KEY,
                Formteilbezeichnung TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        
        # Create Ausführung table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Ausfuehrung (
                Position INTEGER PRIMARY KEY,
                Taetigkeit TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        
        # Create Sonstige Zuschläge table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Sonstige_Zuschlaege (
                Position INTEGER PRIMARY KEY,
                Zuschlag TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        
        # Create Materialpreise table
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
        
        # Fill price_list table if empty
        cursor.execute("SELECT COUNT(*) FROM price_list")
        if cursor.fetchone()[0] == 0:
            csv_path = resource_path('EP_SWF.csv')
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                csvreader = csv.reader(csvfile, delimiter=';')
                next(csvreader)  # Skip header
                for row in csvreader:
                    if row and not row[0].startswith('#'):
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
                        except Exception as e:
                            logging.error(f"Fehler beim Einfügen der Zeile {row}: {e}")

        # Fill Materialpreise table if empty
        cursor.execute("SELECT COUNT(*) FROM Materialpreise")
        if cursor.fetchone()[0] == 0:
            csv_path = resource_path('Materialpreise.CSV')
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                csvreader = csv.reader(csvfile, delimiter=';')
                next(csvreader)  # Skip header
                for row in csvreader:
                    if len(row) == 7:
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
                        except Exception as e:
                            logging.error(f"Fehler beim Einfügen der Zeile {row}: {e}")
        
        # Laden der Formteile-Daten
        cursor.execute("SELECT COUNT(*) FROM Formteile")
        if cursor.fetchone()[0] == 0:
            with open('Formteile.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter=';')
                next(reader)  # Überspringen Sie die Kopfzeile
                for row in reader:
                    if row:
                        cursor.execute('''
                            INSERT INTO Formteile (Position, Formteilbezeichnung, Faktor)
                            VALUES (?, ?, ?)
                        ''', (int(row[0]), row[1], float(row[2].replace(',', '.'))))

        # Laden der Ausführungen-Daten
        cursor.execute("SELECT COUNT(*) FROM Ausfuehrung")
        if cursor.fetchone()[0] == 0:
            try:
                with open('Taetigkeiten.csv', 'r', encoding='utf-8') as file:
                    reader = csv.reader(file, delimiter=';')
                    next(reader)  # Überspringen Sie die Kopfzeile
                    for row in reader:
                        if len(row) == 3:  # Stellen Sie sicher, dass die Zeile 3 Elemente hat
                            try:
                                position = int(row[0])
                                taetigkeit = row[1]
                                faktor = float(row[2].replace(',', '.'))
                                cursor.execute('''
                                    INSERT INTO Ausfuehrung (Position, Taetigkeit, Faktor)
                                    VALUES (?, ?, ?)
                                ''', (position, taetigkeit, faktor))
                            except ValueError as e:
                                logging.warning(f"Fehler beim Verarbeiten der Zeile {row}: {e}")
                        else:
                            logging.warning(f"Ungültige Zeile in Taetigkeiten.csv: {row}")
            except FileNotFoundError:
                logging.error("Die Datei Taetigkeiten.csv wurde nicht gefunden.")
            except csv.Error as e:
                logging.error(f"Fehler beim Lesen der CSV-Datei: {e}")
            except sqlite3.Error as e:
                logging.error(f"Datenbankfehler: {e}")
        
        conn.commit()
        logging.info("Datenbankinitialisierung erfolgreich abgeschlossen.")
    except Exception as e:
        logging.error(f"Fehler bei der Datenbankinitialisierung: {e}")
        conn.rollback()
    finally:
        conn.close()

# Add a new function to insert Materialpreise data
def insert_materialpreise_data(csv_file_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        cursor.execute("DELETE FROM Materialpreise")
        
        # Read CSV file
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile, delimiter=';')
            next(csv_reader)  # Skip the header row
            
            # Prepare data for insertion
            data_to_insert = []
            for row in csv_reader:
                if len(row) != 7:  # Ensure each row has 7 columns
                    logging.warning(f"Skipping invalid row: {row}")
                    continue
                
                rv_pos = int(row[0])
                benennung = row[1]
                material = row[2] if row[2] != '' else None
                abmessung_me = f"{row[3]} {row[4]}".strip()
                ep = float(row[5].replace(',', '.'))  # Replace comma with dot for float conversion
                per = row[6]
                
                data_to_insert.append((rv_pos, benennung, material, abmessung_me, ep, per))
        
        # Insert data
        cursor.executemany('''
            INSERT INTO Materialpreise (RV_Pos, Benennung, Material, Abmessung_ME, EP, per)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', data_to_insert)
        
        conn.commit()
        logging.info(f"{len(data_to_insert)} Materialpreise Einträge erfolgreich eingefügt.")
    except Exception as e:
        logging.error(f"Fehler beim Einfügen der Materialpreise: {e}")
        conn.rollback()
    finally:
        conn.close()

logging.basicConfig(level=logging.DEBUG)

def main(page: ft.Page):
    logging.debug("main function started")
    app = InvoicingApp(page)
    page.add(app)

class InvoicingApp(ft.UserControl):
    def __init__(self, page: ft.Page):
        logging.debug("InvoicingApp initialization started")
        super().__init__()
        self.page = page
        self.items = []
        self.conn = sqlite3.connect('invoicing.db')
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.import_csv_data()

    def create_tables(self):
        # Die Tabellen existieren bereits, also müssen wir sie nicht erneut erstellen
        pass

    def import_csv_data(self):
        csv_files = {
            'price_list': 'EP_SWF.csv',
            'Formteile': 'Formteile.csv',
            'Ausfuehrung': 'Taetigkeiten.csv',
            'Sonstige_Zuschlaege': 'sonstige_zuschlaege.csv'
        }
        
        for table, filename in csv_files.items():
            self.import_csv_to_table(table, filename)

    def import_csv_to_table(self, table, filename):
        file_path = os.path.join(os.path.dirname(__file__), '..', 'content', filename)
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            next(reader)  # Überspringen Sie die Kopfzeile
            to_db = []
            for row in reader:
                to_db.append((row[0], row[1], row[2], row[3], row[4], row[5].replace(',', '.'), row[6], row[1]))

        self.cursor.executemany(f'''
        INSERT OR REPLACE INTO {table} (ID, Item_Number, DN, DA, Size, Value, Unit, Bauteil)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', to_db)
        self.conn.commit()

    def build(self):
        return ft.Column([
            ft.Text("Rechnungs-App"),
            ft.ElevatedButton("Daten laden", on_click=self.load_data),
            # Weitere UI-Elemente hier hinzufügen
        ])

    def load_data(self, e):
        self.cursor.execute("SELECT * FROM price_list LIMIT 10")
        data = self.cursor.fetchall()
        # Hier können Sie die geladenen Daten in der UI anzeigen
        print(data)  # Ersetzen Sie dies durch die tatsächliche UI-Aktualisierung

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)


    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        
        # Initialisierung der UI-Elemente
        self.client_name_dropdown = ft.Dropdown(label="Kundenname", width=300)
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", visible=False)
        self.bestell_nr = ft.TextField(label="Bestell-Nr.", width=200)
        self.bestelldatum = ft.TextField(label="Bestelldatum", width=200)
        self.baustelle = ft.TextField(label="Baustelle", width=200)
        self.anlagenteil = ft.TextField(label="Anlagenteil", width=200)
        self.aufmass_nr = ft.TextField(label="Aufmaß-Nr.", width=200)
        self.aufmassart = ft.Dropdown(
            label="Aufmaßart",
            width=200,
            options=[
                ft.dropdown.Option("Aufmaß"),
                ft.dropdown.Option("Abschlagsrechnung"),
                ft.dropdown.Option("Schlussrechnung")
            ]
        )
        self.auftrags_nr = ft.TextField(label="Auftrags-Nr.", width=200)
        self.ausfuehrungsbeginn = ft.TextField(label="Ausführungsbeginn", width=200)
        self.ausfuehrungsende = ft.TextField(label="Ausführungsende", width=200)
        
        self.items_container = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Beschreibung")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Größe")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen"))
            ],
            rows=[]
        )
        
        self.gesamtpreis_text = ft.Text("Gesamtpreis: €0.00", size=20)

def Aufmass_erstellen(self, e):
    # Validate input fields
    if not self.client_name_dropdown.value or not self.client_email_dropdown.value:
        self.show_snackbar("Bitte füllen Sie alle erforderlichen Felder aus.")
        return
        # Gather invoice data
        invoice_data = {
            "client_name": self.client_name_dropdown.value,
            "client_email": self.client_email_dropdown.value,
            "invoice_date": datetime.now().strftime("%Y-%m-%d"),
            "items": []
        }

        for item in self.items:
            invoice_data["items"].append({
                "description": item["description"].value,
                "dn": item["dn"].value,
                "da": item["da"].value,
                "size": item["size"].value,
                "price": item["price"].value,
                "quantity": item["quantity"].value,
                "taetigkeit": item["taetigkeit"].value  # Ensure 'taetigkeit' is included
            })

        # Save the invoice to the database
        if self.save_invoice(invoice_data):
            self.show_snackbar("Rechnung erfolgreich erstellt.")
            self.clear_form()  # Clear the form after submission
        else:
            self.show_snackbar("Fehler beim Erstellen der Rechnung.")

def clear_form(self):
        # Logic to clear the form fields
        self.client_name_dropdown.value = None
        self.client_email_dropdown.value = None
        self.items.clear()  # Clear the items list
        self.page.update()

def get_taetigkeit_options():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT Taetigkeit FROM Ausfuehrung ORDER BY Taetigkeit')
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

class InvoicingApp:
    def __init__(self):
        self.page = None
        self.items = []
        self.items_container = ft.Column()
        self.gesamtpreis_text = ft.Text("Gesamtpreis: €0.00", size=20)
        self.client_name_dropdown = None
        self.client_email_dropdown = None
        self.client_name_entry = None
        self.client_email_entry = None
        self.taetigkeit_options = get_taetigkeit_options()

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


class InvoicingApp(ft.UserControl):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.conn = sqlite3.connect('invoicing.db')
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.import_csv_data()
        self.items = []
        self.items_container = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Beschreibung")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Größe")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen"))
            ],
            rows=[]
        )
        self.total_field = ft.TextField(label="Gesamtsumme", read_only=True)
        self.client_name_dropdown = None
        self.client_email_dropdown = None
        self.client_name_entry = None
        self.client_email_entry = None
        self.taetigkeit_options = self.get_taetigkeit_options()
        self.kunde = ft.TextField(label="Kunde", width=200)

    def create_tables(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_list (
            ID INTEGER PRIMARY KEY,
            Item_Number TEXT,
            DN REAL,
            DA REAL,
            Size INTEGER,
            Value REAL,
            Unit TEXT,
            Bauteil TEXT
        )
        ''')
        self.conn.commit()

    def import_csv_data(self):
        file_path = os.path.join(os.path.dirname(__file__), '..', 'content', 'price_list.csv')
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)  # Überspringen Sie die Kopfzeile
            to_db = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]) for row in reader]
        
        self.cursor.executemany('''
        INSERT OR REPLACE INTO price_list (ID, Item_Number, DN, DA, Size, Value, Unit, Bauteil)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', to_db)
        self.conn.commit()

    def create_tables(self):
        # Hier definieren wir die Tabellen
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_list (
            ID INTEGER PRIMARY KEY,
            Item_Number TEXT,
            DN REAL,
            DA REAL,
            Size INTEGER,
            Value REAL,
            Unit TEXT,
            Bauteil TEXT
        )
        ''')
        self.conn.commit()

    def import_csv_data(self):
        file_path = os.path.join(os.path.dirname(__file__), '..', 'content', 'EP_SWF.csv')
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader)  # Überspringen Sie die Kopfzeile
            to_db = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]) for row in reader]
        
        self.cursor.executemany('''
        INSERT OR REPLACE INTO price_list (ID, Item_Number, DN, DA, Size, Value, Unit, Bauteil)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', to_db)
        self.conn.commit()

    def add_item(self, e=None):
        new_item = {
            "beschreibung": "",
            "menge": 1,
            "einzelpreis": 0.0,
            "gesamtpreis": 0.0
        }
        self.items.append(new_item)
        self.update_items()

    def update_items(self):
        for index, item in enumerate(self.items):
            item["gesamtpreis"] = item["menge"] * item["einzelpreis"]
            self.update_item_ui(index)
        self.update()

    def update_item(self, index, field, value):
        if 0 <= index < len(self.items):
            self.items[index][field] = value
            if field in ["menge", "einzelpreis"]:
                self.items[index]["gesamtpreis"] = self.items[index]["menge"] * self.items[index]["einzelpreis"]
            self.update_item_ui(index)
        self.update()

    def update_item_ui(self, index):
        # Implementieren Sie hier die Logik zum Aktualisieren der UI-Elemente für einen spezifischen Artikel
        pass

    def on_dn_change(self, e):
        item = e.control.data
        self.update_item_options(item, "dn")

    def on_da_change(self, e):
        item = e.control.data
        self.update_item_options(item, "da")

    def on_size_change(self, e):
        item = e.control.data
        self.update_item_options(item, "size")

    def on_quantity_change(self, e):
        item = e.control.data
        self.update_item_subtotal(item)

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.update_items_ui()

    def add_item(self):
        bauteil_values = self.get_unique_bauteil_values()
        taetigkeit_options = self.get_taetigkeit_options()
        
        new_item = {
            "taetigkeit": ft.Dropdown(
                label="Tätigkeit",
                options=[ft.dropdown.Option(t) for t in taetigkeit_options],
                width=200,
                on_change=self.on_taetigkeit_change
            ),
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                options=[ft.dropdown.Option(b) for b in bauteil_values],
                width=200,
                on_change=self.on_description_change
            ),
            "dn": ft.Dropdown(
                label="DN",
                width=100,
                visible=False,
                on_change=self.on_dn_change
            ),
            "da": ft.Dropdown(
                label="DA",
                width=100,
                visible=False,
                on_change=self.on_da_change
            ),
            "size": ft.Dropdown(
                label="Dämmdicke",
                width=100,
                visible=False,
                on_change=self.on_size_change
            ),
            "price": ft.TextField(
                label="Einheitspreis",
                width=100,
                read_only=True
            ),
            "quantity": ft.TextField(
                label="Menge",
                width=100,
                on_change=self.on_quantity_change
            ),
            "zwischensumme": ft.TextField(
                label="Zwischensumme",
                width=100,
                read_only=True
            ),
            "remove_button": ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                tooltip="Entfernen",
                on_click=lambda _: self.remove_item(new_item)
            )
        }
        
        # Setze das 'data' Attribut für jedes Control auf das gesamte Item
        for control in new_item.values():
            if isinstance(control, ft.Control):
                control.data = new_item

        self.items.append(new_item)
        self.update_items_ui()
        self.update_item_options(new_item, "description")  # Initialize options for the new item

    def on_taetigkeit_change(self, e):
        item = e.control.data
        self.update_item_subtotal(item)

    def on_description_change(self, e):
        item = e.control.data
        self.update_item_options(item, "description")

    def load_taetigkeiten(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Taetigkeit FROM Ausfuehrung ORDER BY Position')
            taetigkeiten = [row[0] for row in cursor.fetchall()]
            if not taetigkeiten:
                logging.warning("Keine Tätigkeiten in der Datenbank gefunden.")
                taetigkeiten = ["Standard"]  # Fügen Sie eine Standardoption hinzu
            return taetigkeiten
        except sqlite3.Error as e:
            logging.error(f"Fehler beim Laden der Tätigkeiten: {e}")
            return ["Standard"]  # Rückgabe einer Standardoption im Fehlerfall
        finally:
            cursor.close()
            conn.close()

    def add_item(self):
        bauteil_values = self.get_unique_bauteil_values()
        taetigkeit_options = self.get_taetigkeit_options()
        
        new_item = {
            "taetigkeit": ft.Dropdown(
                label="Tätigkeit",
                options=[ft.dropdown.Option(t) for t in taetigkeit_options],
                width=200,
                on_change=self.on_taetigkeit_change
            ),
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                options=[ft.dropdown.Option(b) for b in bauteil_values],
                width=200,
                on_change=self.on_description_change
            ),
            "dn": ft.Dropdown(
                label="DN",
                width=100,
                visible=False,
                on_change=self.on_dn_change
            ),
            "da": ft.Dropdown(
                label="DA",
                width=100,
                visible=False,
                on_change=self.on_da_change
            ),
            "size": ft.Dropdown(
                label="Dämmdicke",
                width=100,
                visible=False,
                on_change=self.on_size_change
            ),
            "price": ft.TextField(
                label="Einheitspreis",
                width=100,
                read_only=True
            ),
            "quantity": ft.TextField(
                label="Menge",
                width=100,
                on_change=self.on_quantity_change
            ),
            "zwischensumme": ft.TextField(
                label="Zwischensumme",
                width=100,
                read_only=True
            ),
            "remove_button": ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                tooltip="Entfernen",
                on_click=lambda _: self.remove_item(new_item)
            )
        }
        
        # Setze das 'data' Attribut für jedes Control auf das gesamte Item
        for control in new_item.values():
            if isinstance(control, ft.Control):
                control.data = new_item

        self.items.append(new_item)
        self.update_items_ui()
        self.update_item_options(new_item, "description")  # Initialize options for the new item

    def on_description_change(self, e):
        item = e.control.data
        self.update_item_options(item, "description")
        self.update_item_subtotal(item)

    def update_item_subtotal(self, item):
        menge = float(item.menge.value) if item.menge.value else 0
        einzelpreis = float(item.einzelpreis.value) if item.einzelpreis.value else 0
        item.zwischensumme.value = f"{menge * einzelpreis:.2f}"
        self.update_gesamtpreis()

    def find_item_index(self, item):
        return next((i for i, x in enumerate(self.items) if x == item), -1)

    def update_gesamtpreis(self):
        gesamtpreis = sum(float(item.zwischensumme.value) for item in self.items if item.zwischensumme.value)
        self.gesamtpreis.value = f"{gesamtpreis:.2f}"
        self.update()

    def build_ui(self):
        # Kundeninformationen
        self.client_name_dropdown = ft.Dropdown(label="Kundenname", width=300)
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", visible=False)
        
        # Rechnungsdetails
        self.bestell_nr = ft.TextField(label="Bestell-Nr.", width=200)
        self.bestelldatum = ft.TextField(label="Bestelldatum", width=200)
        self.baustelle = ft.TextField(label="Baustelle", width=200)
        self.anlagenteil = ft.TextField(label="Anlagenteil", width=200)
        self.aufmass_nr = ft.TextField(label="Aufmaß-Nr.", width=200)
        self.aufmassart = ft.Dropdown(
            label="Aufmaßart",
            width=200,
            options=[
                ft.dropdown.Option("Aufmaß"),
                ft.dropdown.Option("Abschlagsrechnung"),
                ft.dropdown.Option("Schlussrechnung")
            ]
        )
        self.auftrags_nr = ft.TextField(label="Auftrags-Nr.", width=200)
        self.ausfuehrungsbeginn = ft.TextField(label="Ausführungsbeginn", width=200)
        self.ausfuehrungsende = ft.TextField(label="Ausführungsende", width=200)

        # Rechnungspositionen
        self.items_container = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Beschreibung")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Größe")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen"))
            ],
            rows=[]
        )

        self.total_field = ft.TextField(label="Gesamtsumme", read_only=True)

        add_item_button = ft.ElevatedButton("Position hinzufügen", on_click=self.add_item)
        save_button = ft.ElevatedButton("Rechnung speichern", on_click=self.save_invoice)
        generate_pdf_button = ft.ElevatedButton("PDF generieren", on_click=self.generate_pdf)

        return ft.Column([
            ft.Row([self.client_name_dropdown]),
            ft.Row([self.client_name_entry]),
            ft.Row([self.bestell_nr, self.bestelldatum, self.baustelle]),
            ft.Row([self.anlagenteil, self.aufmass_nr, self.aufmassart]),
            ft.Row([self.auftrags_nr, self.ausfuehrungsbeginn, self.ausfuehrungsende]),
            self.items_container,
            ft.Row([add_item_button, save_button, generate_pdf_button]),
            self.total_field
        ])

    def generate_pdf(self, e):
        # Hier sammeln Sie die Rechnungsdaten aus den UI-Elementen
        rechnungsdaten = self.collect_invoice_data()
        pdf_dateiname = self.pdf_generieren(rechnungsdaten)
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text(f"PDF wurde generiert: {pdf_dateiname}")))

    def collect_invoice_data(self):
        # Implementieren Sie hier die Logik zum Sammeln der Rechnungsdaten aus den UI-Elementen
        # Dies ist nur ein Beispiel und muss an Ihre spezifische UI angepasst werden
        return {
            'client_name': self.kunde.value,
            'invoice_date': datetime.now().strftime('%Y-%m-%d'),
            'items': [
                {
                    'taetigkeit': 'Beispieltätigkeit',
                    'description': 'Beschreibung',
                    'dn': 'DN Wert',
                    'da': 'DA Wert',
                    'size': 'Größe',
                    'price': 100.00,
                    'quantity': 1
                }
            ],
            'total': 100.00
        }

    def get_price(self, bauteil, dn, da, size):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                # Für Formteile
                cursor.execute('''
                    SELECT Faktor FROM Formteile 
                    WHERE Formteilbezeichnung = ?
                ''', (bauteil,))
                formteil_faktor = cursor.fetchone()
                if formteil_faktor:
                    # Hole den Basispreis für Rohrleitungen
                    cursor.execute('''
                        SELECT value FROM price_list 
                        WHERE bauteil = 'Rohrleitung' AND dn = ? AND da = ? AND size = ?
                    ''', (dn, da, size))
                    base_price = cursor.fetchone()
                    if base_price:
                        return base_price[0] * formteil_faktor[0]
            else:
                # Für normale Bauteile
                cursor.execute('''
                    SELECT value FROM price_list 
                    WHERE bauteil = ? AND dn = ? AND da = ? AND size = ?
                ''', (bauteil, dn, da, size))
                price = cursor.fetchone()
                if price:
                    return price[0]
            return 0  # Rückgabe 0, wenn kein Preis gefunden wurde
        finally:
            conn.close()

    def is_formteil(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def update_price(self, item):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        price = self.get_price(bauteil, dn, da, size)
        item["price"].value = f"{price:.2f}"
        self.update_item_subtotal(item)

    def get_da_options(self, bauteil, dn):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                # Für Formteile, verwende Rohrleitung-Optionen
                cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY da', ('Rohrleitung', dn))
            else:
                cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY da', (bauteil, dn))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_size_options(self, bauteil, dn, da):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                # Für Formteile, verwende Rohrleitung-Optionen
                if da:
                    cursor.execute('SELECT DISTINCT size FROM price_list WHERE bauteil = ? AND dn = ? AND da = ? AND value IS NOT NULL AND value != 0 ORDER BY size', ('Rohrleitung', dn, da))
                else:
                    cursor.execute('SELECT DISTINCT size FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY size', ('Rohrleitung', dn))
            else:
                if da:
                    cursor.execute('SELECT DISTINCT size FROM price_list WHERE bauteil = ? AND dn = ? AND da = ? AND value IS NOT NULL AND value != 0 ORDER BY size', (bauteil, dn, da))
                else:
                    cursor.execute('SELECT DISTINCT size FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY size', (bauteil, dn))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_item_options(self, item, changed_field):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value

        if changed_field == "description":
            options = self.get_available_options(bauteil)
            
            dn_values = sorted(set(option[0] for option in options if option[0] is not None))
            da_values = sorted(set(option[1] for option in options if option[1] is not None))
            size_values = sorted(set(option[2] for option in options if option[2] is not None))
            
            item["dn"].options = [ft.dropdown.Option(str(dn)) for dn in dn_values]
            item["da"].options = [ft.dropdown.Option(str(da)) for da in da_values]
            item["size"].options = [ft.dropdown.Option(str(size)) for size in size_values]
            
            item["dn"].visible = bool(dn_values)
            item["da"].visible = bool(da_values)
            item["size"].visible = bool(size_values)
        elif changed_field == "dn":
            da_options = self.get_da_options(bauteil, dn)
            item["da"].options = [ft.dropdown.Option(str(da)) for da in da_options]
            item["da"].value = None
            size_options = self.get_size_options(bauteil, dn, None)
            item["size"].options = [ft.dropdown.Option(str(size)) for size in size_options]
            item["size"].value = None
        elif changed_field == "da":
            size_options = self.get_size_options(bauteil, dn, da)
            item["size"].options = [ft.dropdown.Option(str(size)) for size in size_options]
            item["size"].value = None

        self.update_price(item)
        
        if self.page:
            self.page.update()

    def save_invoice(self, invoice_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            total = invoice_data.get('total', 0)  # Default to 0 if 'total' is not in invoice_data
            if total is None:
                total = 0
            cursor.execute('''
                INSERT INTO invoices (client_name, bestell_nr, bestelldatum, baustelle, anlagenteil, 
                                      aufmass_nr, aufmassart, auftrags_nr, ausfuehrungsbeginn, 
                                      ausfuehrungsende, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_data['client_name'], invoice_data['bestell_nr'], invoice_data['bestelldatum'],
                  invoice_data['baustelle'], invoice_data['anlagenteil'], invoice_data['aufmass_nr'],
                  invoice_data['aufmassart'], invoice_data['auftrags_nr'], invoice_data['ausfuehrungsbeginn'],
                  invoice_data['ausfuehrungsende'], total))
            
            invoice_id = cursor.lastrowid
            
            for item in invoice_data['items']:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, taetigkeit, item_description, dn, da, size, item_price, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, item['taetigkeit'], item['description'], item['dn'], item['da'], 
                      item['size'], item['price'], item['quantity']))
            
            conn.commit()
            return invoice_id
        except sqlite3.Error as e:
            print(f"Ein Fehler ist aufgetreten: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()

    def Aufmass_erstellen(self, e):
        if not self.client_name_dropdown.value:
            self.show_snackbar("Bitte wählen Sie einen Kunden aus.")
            return
        
        invoice_data = {
            "client_name": self.client_name_dropdown.value,
            "bestell_nr": self.bestell_nr_dropdown.value if hasattr(self, 'bestell_nr_dropdown') else None,
            "bestelldatum": self.bestelldatum_picker.value if hasattr(self, 'bestelldatum_picker') else None,
            "baustelle": self.baustelle_dropdown.value if hasattr(self, 'baustelle_dropdown') else None,
            "anlagenteil": self.anlagenteil_dropdown.value if hasattr(self, 'anlagenteil_dropdown') else None,
            "aufmass_nr": self.aufmass_nr_field.value if hasattr(self, 'aufmass_nr_field') else None,
            "aufmassart": self.aufmassart_dropdown.value if hasattr(self, 'aufmassart_dropdown') else None,
            "auftrags_nr": self.auftrags_nr_dropdown.value if hasattr(self, 'auftrags_nr_dropdown') else None,
            "ausfuehrungsbeginn": self.ausfuehrungsbeginn_picker.value if hasattr(self, 'ausfuehrungsbeginn_picker') else None,
            "ausfuehrungsende": self.ausfuehrungsende_picker.value if hasattr(self, 'ausfuehrungsende_picker') else None,
            "total": self.calculate_total(),
            "items": [
                {
                    "taetigkeit": item["taetigkeit"].value,
                    "description": item["description"].value,
                    "dn": item["dn"].value,
                    "da": item["da"].value,
                    "size": item["size"].value,
                    "price": item["price"].value,
                    "quantity": item["quantity"].value
                } for item in self.items
            ]
        }

        if self.save_invoice(invoice_data):
            self.show_snackbar("Aufmaß erfolgreich erstellt und gespeichert.")
            self.reset_form()
        else:
            self.show_snackbar("Fehler beim Speichern des Aufmaßes.")

        self.page.update()

    def get_available_options(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                # For Formteile, use Rohrleitung options
                cursor.execute('SELECT dn, da, size FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0', ('Rohrleitung',))
            else:
                cursor.execute('SELECT dn, da, size FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0', (bauteil,))
            options = cursor.fetchall()
            return options
        finally:
            conn.close()

    def rechnung_ohne_preise_generieren(self, e):
        if not self.client_name_dropdown.value or not self.items:
            self.show_snackbar("Bitte füllen Sie alle erforderlichen Felder aus und fügen Sie mindestens einen Artikel hinzu.")
            return
        
        client_name = self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value
        
        invoice_date = datetime.now().strftime("%Y-%m-%d")
        
        invoice_items = [
            {
                "taetigkeit": item["taetigkeit"].value,
                "description": item["description"].value,
                "dn": item["dn"].value,
                "da": item["da"].value,
                "size": item["size"].value,
                "quantity": int(item["quantity"].value)
            }
            for item in self.items
        ]
        
        invoice_data = {
            "client_name": client_name,
            "invoice_date": invoice_date,
            "items": invoice_items
        }
        
        pdf_path = self.pdf_generieren_ohne_preise(invoice_data)
        self.show_snackbar(f"Rechnung ohne Preise erstellt und gespeichert als: {pdf_path}")

    def rechnung_speichern(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Fügen Sie die Rechnung in die invoices Tabelle ein
            cursor.execute('''
                INSERT INTO invoices (client_name, client_email, invoice_date, total)
                VALUES (?, ?, ?, ?)
            ''', (self.client_name_dropdown.value, self.client_email_dropdown.value, 
                  datetime.now().strftime("%Y-%m-%d"), self.calculate_total()))
            
            invoice_id = cursor.lastrowid
            
            # Fügen Sie die Rechnungspositionen in die invoice_items Tabelle ein
            for item in self.items:
                taetigkeit_value = item["taetigkeit"].value
                print(f"Speichere Tätigkeit: {taetigkeit_value}")  # Debugging-Ausgabe
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity, taetigkeit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id,
                    item["description"].value,
                    item["dn"].value,
                    item["da"].value,
                    item["size"].value,
                    item["price"].value,
                    item["quantity"].value,
                    taetigkeit_value
                ))
                print(f"Gespeichertes Item: {cursor.lastrowid}")  # Debugging-Ausgabe
            
            conn.commit()
            self.show_snackbar("Rechnung erfolgreich gespeichert")
            return True
        except sqlite3.Error as e:
            print(f"Ein Fehler ist aufgetreten: {e}")
            conn.rollback()
            self.show_snackbar("Fehler beim Speichern der Rechnung")
            return False
        finally:
            conn.close()

    def calculate_total(self):
        return sum(float(item["zwischensumme"].value) for item in self.items if item["zwischensumme"].value)

    def pdf_generieren_ohne_preise(self, rechnungsdaten):
        from reportlab.lib.pagesizes import landscape, A4
        # Get the root directory (where the script or exe is located)
        if getattr(sys, 'frozen', False):
            # If running as compiled executable
            root_dir = os.path.dirname(sys.executable)
        else:
            # If running as script
            root_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Generate a unique filename
        pdf_dateiname = f"Rechnung_ohne_Preise_{rechnungsdaten['client_name']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_path = os.path.join(root_dir, pdf_dateiname)

        # Create the PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=landscape(A4))
        elements = []

        # Add invoice details
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Rechnung für: {rechnungsdaten['client_name']}", styles['Heading1']))
        elements.append(Paragraph(f"Datum: {rechnungsdaten['invoice_date']}", styles['Normal']))
        elements.append(Paragraph(" ", styles['Normal']))  # Add some space

        # Create the table for invoice items
        data = [['Beschreibung', 'DN', 'DA', 'Größe', 'Menge']]
        for item in rechnungsdaten['items']:
            row = [
                item['description'],
                item['dn'],
                item['da'],
                item['size'],
                str(item['quantity'])
            ]
            data.append(row)

        # Create the table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)

        # Build the PDF
        doc.build(elements)

        return pdf_path

    def main(self, page: ft.Page):
        self.page = page
        self.page.title = "Rechnungserstellung"
        self.page.window.width = 1200
        self.page.window.height = 800
        self.page.window.resizable = True
        self.page.padding = 20
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.fonts = {
            "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
        }
        self.page.theme = ft.Theme(font_family="Roboto")

        self.items = []  # Initialize the items list
        main_view = self.build_ui()
        self.page.add(main_view)
        self.add_item()  # Add an empty item line on initial load
        self.page.update()

    def main(self, page: ft.Page):
        page.title = "Rechnungs-App"
        page.add(self)
        self.add_item()  # Add an empty item line on initial load

    def route_change(self, route):
        # This method will be called when the route changes
        # You can implement routing logic here if needed
        pass

    def toggle_name_entry(self):
        if self.client_name_dropdown.value == "Neuer Kunde":
            self.client_name_entry.visible = True
        else:
            self.client_name_entry.visible = False
        self.page.update()

    def toggle_email_entry(self):
        if self.client_email_dropdown.value == "Neue E-Mail":
            self.client_email_entry.visible = True
        else:
            self.client_email_entry.visible = False
        self.page.update()

    def rechnungen_anzeigen(self, e):
        rechnungen = self.rechnungen_abrufen()
        
        # Create the DataTable
        columns = [
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Kundenname")),
            ft.DataColumn(ft.Text("Bestellnummer")),
            ft.DataColumn(ft.Text("Datum")),
            ft.DataColumn(ft.Text("Gesamt")),
            ft.DataColumn(ft.Text("Aktionen"))
        ]
        
        rows = []
        for rechnung in rechnungen:
            # Handle the case where the total might be None
            total = rechnung[4] if rechnung[4] is not None else 0
            total_formatted = f"€{total:.2f}"
            
            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(rechnung[0]))),
                    ft.DataCell(ft.Text(rechnung[1])),
                    ft.DataCell(ft.Text(rechnung[2])),
                    ft.DataCell(ft.Text(rechnung[3])),
                    ft.DataCell(ft.Text(total_formatted)),
                    ft.DataCell(
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.VISIBILITY,
                                tooltip="Anzeigen",
                                on_click=lambda _, id=rechnung[0]: self.rechnung_anzeigen(id)
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                tooltip="Löschen",
                                on_click=lambda _, id=rechnung[0]: self.rechnung_loeschen_dialog(id)
                            )
                        ])
                    )
                ]
            )
            rows.append(row)
        
        rechnungen_tabelle = ft.DataTable(
            columns=columns,
            rows=rows,
        )
        
        # Clear existing content and add the table
        self.page.controls.clear()
        self.page.add(
            ft.Text("Rechnungsübersicht", size=20, weight="bold"),
            rechnungen_tabelle,
            ft.ElevatedButton("Zurück", on_click=self.show_main_view)
        )
        self.page.update()

    def get_unique_client_names(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT client_name FROM invoices ORDER BY client_name')
        names = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out empty names
        conn.close()
        return names

    def get_unique_customer_emails(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT client_email FROM invoices ORDER BY client_email')
        emails = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out empty emails
        conn.close()
        return emails

    def rechnung_loeschen_dialog(self, rechnung_id):
        def close_dialog(e):
            self.page.dialog.open = False
            self.page.update()

        def confirm_delete(e):
            if self.rechnung_loeschen(rechnung_id):
                self.show_snackbar(f"Rechnung {rechnung_id} wurde gelöscht.")
                self.rechnungen_anzeigen(None)  # Aktualisiere die Rechnungsliste
            else:
                self.show_snackbar(f"Fehler beim Löschen der Rechnung {rechnung_id}.")
            close_dialog(e)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rechnung löschen"),
            content=ft.Text(f"Möchten Sie die Rechnung {rechnung_id} wirklich löschen?"),
            actions=[
                ft.TextButton("Abbrechen", on_click=close_dialog),
                ft.TextButton("Löschen", on_click=confirm_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def rechnung_bearbeiten(self, rechnung_id):
        # Close the invoice list dialog if open
        if self.page.dialog:
            self.page.dialog.open = False

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Fetch invoice details
            cursor.execute('''
                SELECT i.*, ii.id as item_id, ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity
                FROM invoices i
                LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
                WHERE i.id = ?
            ''', (rechnung_id,))
            
            results = cursor.fetchall()
            
            if not results:
                self.show_snackbar("Rechnung nicht gefunden")
                return
            
            # Process the results
            invoice_data = {
                "id": results[0][0],
                "client_name": results[0][1],
                "client_email": results[0][2],
                "invoice_date": results[0][3],
                "total": results[0][4],
                "items": []
            }
            
            for row in results:
                if row[5]:  # Check if there's an item (item_id is not None)
                    invoice_data["items"].append({
                        "id": row[5],
                        "description": row[6],
                        "dn": row[7],
                        "da": row[8],
                        "size": row[9],
                        "price": row[10],
                        "quantity": row[11]
                    })
            
            # Populate the form with the fetched data
            self.populate_form(invoice_data)
            
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            self.show_snackbar("Fehler beim Laden der Rechnung")
        finally:
            conn.close()

    def rechnung_bearbeiten(self, rechnung_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.*, ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity, ii.subtotal, ii.taetigkeit
            FROM invoices i
            LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
            WHERE i.id = ?
        ''', (rechnung_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self.show_snackbar(f"Rechnung mit ID {rechnung_id} nicht gefunden.")
            return

        # Clear existing items
        self.items.clear()
        self.items_container.controls.clear()

        # Populate form with invoice details
        invoice_data = {
            "id": rows[0][0],
            "client_name": rows[0][1],
            "client_email": rows[0][2],
            "invoice_date": rows[0][3],
            "total": rows[0][4],
            "items": []
        }

        for row in rows:
            item = {
                "taetigkeit": row[9],
                "description": row[5],
                "dn": row[6],
                "da": row[7],
                "size": row[8],
                "price": row[9],
                "quantity": row[10],
                "zwischensumme": row[11]
            }
            invoice_data["items"].append(item)

        self.populate_form(invoice_data)

    def populate_form(self, invoice_data):
        # Set client name and email
        self.client_name_dropdown.value = invoice_data["client_name"]
        self.client_email_dropdown.value = invoice_data["client_email"]

        # Add items
        for item in invoice_data["items"]:
            self.add_item_to_form(item)

        # Update total
        self.update_gesamtpreis()

        # Update the page
     
     
        self.page.update()

    def pdf_generieren(self, rechnungsdaten):
        pdf_dateiname = f"Rechnung_{rechnungsdaten['client_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_pfad = os.path.join(os.path.expanduser("~"), "Downloads", pdf_dateiname)
        
        # A4 im Querformat verwenden
        dok = SimpleDocTemplate(pdf_pfad, pagesize=landscape(A4))
        elemente = []
        
        # Verbesserte Stile
        stile = getSampleStyleSheet()
        stile.add(ParagraphStyle(name='Zentriert', alignment=1))
        stile.add(ParagraphStyle(name='Rechts', alignment=2))
        
        # Firmenlogo (falls vorhanden)
        logo_pfad = resource_path("Assets/KAE_Logo_RGB_300dpi2.png")
        if os.path.exists(logo_pfad):
            logo = Image(logo_pfad)
            logo.drawHeight = 4*inch
            logo.drawWidth = 4*inch
            elemente.append(logo)
        
        # Rechnungsdetails
        elemente.append(Paragraph(f"Rechnung für: {rechnungsdaten['client_name']}", stile['Heading1']))
        elemente.append(Paragraph(f"Datum: {rechnungsdaten['invoice_date']}", stile['Normal']))
        elemente.append(Spacer(1, 0.25*inch))
        
        # Tabelle für Rechnungspositionen
        daten = [['Tätigkeit', 'Beschreibung', 'DN', 'DA', 'Größe', 'Preis', 'Menge', 'Zwischensumme']]
        for position in rechnungsdaten['items']:
            zeile = [
                position.get('taetigkeit', ''),
                position['description'],
                position.get('dn', ''),
                position.get('da', ''),
                position['size'],
                f"€{position['price']:.2f}",
                str(position['quantity']),
                f"€{float(position['price']) * float(position['quantity']):.2f}"
            ]
            daten.append(zeile)
        
        # Gesamtbetrag
        daten.append(['', '', '', '', '', '', 'Gesamtbetrag:', f"€{rechnungsdaten['total']:.2f}"])
        
        # Tabelle mit angepassten Spaltenbreiten erstellen
        spaltenbreiten = [6*cm, 4*cm, 1.5*cm, 1.5*cm, 2*cm, 2*cm, 1.5*cm, 3.5*cm]
        tabelle = Table(daten, colWidths=spaltenbreiten)
        
        # Tabellenstil
        tabellenstil = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, -1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
            ('TOPPADDING', (0, -1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 2, colors.black),
        ])
        tabelle.setStyle(tabellenstil)
        
        elemente.append(tabelle)
        
        elemente.append(Spacer(1, 0.5*inch))
        elemente.append(Paragraph("Vielen Dank für Ihr Geschäft!", stile['Zentriert']))
        
        # PDF generieren
        dok.build(elemente)
        
        return pdf_dateiname

    def populate_form(self, invoice_data):
        # Kundendaten setzen
        self.client_name_dropdown.value = invoice_data["client_name"]
        self.client_email_dropdown.value = invoice_data["client_email"]
        
        # Bestehende Elemente löschen
        self.items.clear()
        self.items_container.controls.clear()
        
        # Elemente hinzufügen
        for item in invoice_data["items"]:
            new_item = self.add_item_to_form(item)
            new_item["taetigkeit"].value = item["taetigkeit"]
            new_item["description"].value = item["description"]
            new_item["dn"].value = item["dn"]
            new_item["da"].value = item["da"]
            new_item["size"].value = item["size"]
            new_item["price"].value = str(item["price"])
            new_item["quantity"].value = str(item["quantity"])
            new_item["zwischensumme"].value = str(item["zwischensumme"])
            self.update_item_subtotal(new_item)
        
        # Gesamtpreis aktualisieren
        self.update_gesamtpreis()
        
        # Seite aktualisieren
        self.page.update()

    def rechnung_bearbeiten(self, rechnung_id):
        # Close the invoice list dialog if open
        if self.page.dialog:
            self.page.dialog.open = False

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.*, ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity, ii.taetigkeit
            FROM invoices i
            LEFT JOIN invoice_items ii ON i.id = ii.invoice_id
            WHERE i.id = ?
        ''', (rechnung_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self.show_snackbar(f"Rechnung mit ID {rechnung_id} nicht gefunden.")
            return

        # Bestehende Elemente löschen
        self.items.clear()
        self.items_container.controls.clear()

        # Formular mit Rechnungsdetails befüllen
        invoice_data = {
            "id": rows[0][0],
            "client_name": rows[0][1],
            "client_email": rows[0][2],
            "invoice_date": rows[0][3],
            "total": rows[0][4],
            "items": []
        }

        for row in rows:
            item = {
                "taetigkeit": row[11],  # Stellen Sie sicher, dass dies der korrekte Index für taetigkeit ist
                "description": row[5],
                "dn": row[6],
                "da": row[7],
                "size": row[8],
                "price": row[9],
                "quantity": row[10],
                "zwischensumme": float(row[9]) * float(row[10])
            }
            invoice_data["items"].append(item)

        self.populate_form(invoice_data)
        self.page.update()

    def add_item_to_form(self, item):
        # Create a new item dictionary similar to the one in add_item method
        new_item = {
            "description": ft.Dropdown(
                width=200,
                value=item["description"],
                on_change=lambda e: self.update_item_options(new_item, "description")
            ),
            "dn": ft.Dropdown(width=100, value=str(item["dn"])),
            "da": ft.Dropdown(width=100, value=str(item["da"])),
            "size": ft.Dropdown(width=100, value=item["size"]),
            "price": ft.TextField(width=100, value=str(item["price"])),
            "quantity": ft.TextField(width=50, value=str(item["quantity"])),
            "subtotal": ft.Text("0.00", width=100),
            "remove_button": ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                tooltip="Entfernen",
                on_click=self.create_remove_handler(len(self.items))
            ),
        }
        self.items.append(new_item)
        self.update_item_subtotal(new_item)

    def add_item_to_form(self, item=None):
        if item is None:
            item = {
                "taetigkeit": "",
                "description": "",
                "dn": "",
                "da": "",
                "size": "",
                "price": 0,
                "quantity": 1,
            }

        taetigkeit_dropdown = ft.Dropdown(
            label="Tätigkeit",
            width=300,
            options=[ft.dropdown.Option(t) for t in self.taetigkeiten],
            value=item["taetigkeit"],
            on_change=lambda e: self.update_item(item, "taetigkeit", e.control.value)
        )
        description_dropdown = ft.Dropdown(
            label="Artikelbeschreibung",
            width=300,
            options=[ft.dropdown.Option(b) for b in self.get_unique_bauteil_values()],
            value=item["description"],
            on_change=lambda e: self.update_item(item, "description", e.control.value)
        )
        dn_dropdown = ft.Dropdown(
            label="DN",
            width=150,
            visible=False,
            value=item["dn"],
            on_change=lambda e: self.update_item(item, "dn", e.control.value)
        )
        da_dropdown = ft.Dropdown(
            label="DA",
            width=150,
            visible=False,
            value=item["da"],
            on_change=lambda e: self.update_item(item, "da", e.control.value)
        )
        size_dropdown = ft.Dropdown(
            label="Dämmdicke",
            width=150,
            value=item["size"],
            on_change=lambda e: self.update_item(item, "size", e.control.value)
        )
        price_field = ft.TextField(
            label="Einheitspreis",
            width=100,
            value=str(item["price"]),
            read_only=True
        )
        quantity_field = ft.TextField(
            label="Menge",
            width=50,
            value=str(item["quantity"]),
            on_change=lambda e: self.update_item(item, "quantity", e.control.value)
        )

        # Fügen Sie die UI-Elemente zur Seite hinzu
        self.items_container.rows.append(ft.DataRow(
            cells=[
                ft.DataCell(taetigkeit_dropdown),
                ft.DataCell(description_dropdown),
                ft.DataCell(dn_dropdown),
                ft.DataCell(da_dropdown),
                ft.DataCell(size_dropdown),
                ft.DataCell(price_field),
                ft.DataCell(quantity_field),
                ft.DataCell(ft.Text("")),  # Placeholder for Zwischensumme
                ft.DataCell(ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    on_click=lambda _: self.remove_item(item)
                )),
            ]
        ))

        if item not in self.items:
            self.items.append(item)
        self.update_items_ui()
        self.page.update()

        return item

    def get_taetigkeit_options(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Taetigkeit FROM Ausfuehrung ORDER BY Position')
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def update_items_ui(self):
        self.items_container.controls.clear()
        for item in self.items:
            row = ft.Row(controls=[
                item["taetigkeit"],
                item["description"],
                item["dn"],
                item["da"],
                item["size"],
                item["price"],
                item["quantity"],
                item["zwischensumme"],
                item["remove_button"]
            ])
            self.items_container.controls.append(row)
        if self.page:
            self.page.update()


    def add_item(self, e=None):
        new_item = {
            "beschreibung": "",
            "menge": 1,
            "einzelpreis": 0.0,
            "gesamtpreis": 0.0
        }
        self.items.append(new_item)
        self.update_items()

    def update_items(self):
        for index, item in enumerate(self.items):
            item["gesamtpreis"] = item["menge"] * item["einzelpreis"]
            self.update_item_ui(index)
        self.update_ui()

    def update_item(self, index, field, value):
        if 0 <= index < len(self.items):
            self.items[index][field] = value
            if field in ["menge", "einzelpreis"]:
                self.items[index]["gesamtpreis"] = self.items[index]["menge"] * self.items[index]["einzelpreis"]
            self.update_item_ui(index)
        self.update_ui()

    def update_item_ui(self, index):
        # Implementieren Sie hier die Logik zum Aktualisieren der UI-Elemente für einen spezifischen Artikel
        pass

    def update_ui(self):
        # Implementieren Sie hier die Logik zum Aktualisieren der gesamten UI
        self.update()  # Dies ist die Flet-Methode zum Aktualisieren der UI

    def update_items(self):
        for index, item in enumerate(self.items):
            item["gesamtpreis"] = item["menge"] * item["einzelpreis"]
            self.update_item_ui(index)
        self.update_ui()

    def update_item(self, index, field, value):
        if 0 <= index < len(self.items):
            self.items[index][field] = value
            if field in ["menge", "einzelpreis"]:
                self.items[index]["gesamtpreis"] = self.items[index]["menge"] * self.items[index]["einzelpreis"]
            self.update_item_ui(index)
        self.update_ui()

    def update_item_ui(self, index):
        # Implementieren Sie hier die Logik zum Aktualisieren der UI-Elemente für einen spezifischen Artikel
        pass

    def update_ui(self):
        # Implementieren Sie hier die Logik zum Aktualisieren der gesamten UI
        self.update()  # Dies ist die Flet-Methode zum Aktualisieren der UI

    def update_items(self):
        # Aktualisiert alle Artikel
        for index, item in enumerate(self.items):
            item["gesamtpreis"] = item["menge"] * item["einzelpreis"]
            # Aktualisiere die UI-Elemente für diesen Artikel
            self.update_item_ui(index)
        self.update()  # Direkt die update()-Methode von UserControl aufrufen

    def update_item(self, index, field, value):
        # Aktualisiert ein spezifisches Feld eines Artikels
        if 0 <= index < len(self.items):
            self.items[index][field] = value
            if field in ["menge", "einzelpreis"]:
                self.items[index]["gesamtpreis"] = self.items[index]["menge"] * self.items[index]["einzelpreis"]
            self.update_item_ui(index)
        self.update()

    def update_item_ui(self, index):
        # Implementieren Sie hier die Logik zum Aktualisieren der UI-Elemente für einen spezifischen Artikel
        pass

    def update_item(self):  # Stellen Sie sicher, dass diese Methode existiert
        # Implementieren Sie hier die Logik zum Aktualisieren der Artikel
        # Zum Beispiel:
        for item in self.items:
            item["gesamtpreis"] = item["menge"] * item["einzelpreis"]
        self.update()  # Aktualisiert die UI

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.update_items_ui()

    def update_item(self, index, field, value):
        if 0 <= index < len(self.items):
            self.items[index][field] = value
            if field in ["menge", "einzelpreis"]:
                self.items[index]["gesamtpreis"] = self.items[index]["menge"] * self.items[index]["einzelpreis"]
            self.update_item_ui(index)
        self.update()  # Direkt die update()-Methode von UserControl aufrufen

    def ensure_item_consistency(self, item):
        # Hier wird das default_item verwendet, das bereits in der Klasse definiert ist
        for key, default_value in self.default_item.items():
            if key not in item:
                item[key] = default_value
            elif not isinstance(item[key], type(default_value)):
                try:
                    item[key] = type(default_value)(item[key])
                except ValueError:
                    item[key] = default_value

    def update_total(self):
        total = sum(float(item.get("price", 0)) * float(item.get("quantity", 0)) for item in self.items)
        self.total_field.value = f"€{total:.2f}"
        if self.page:
            self.page.update()

    def update_items_ui(self):
        self.items_container.rows.clear()
        
        for index, item in enumerate(self.items):
            price = item.get("price", 0)
            quantity = item.get("quantity", 0)
            
            # Konvertieren Sie Strings zu Floats, falls nötig
            if isinstance(price, str):
                price = float(price) if price.replace('.', '').isdigit() else 0
            if isinstance(quantity, str):
                quantity = float(quantity) if quantity.replace('.', '').isdigit() else 0
            
            zwischensumme = price * quantity

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(item.get("taetigkeit", "")))),
                    ft.DataCell(ft.Text(str(item.get("description", "")))),
                    ft.DataCell(ft.Text(str(item.get("dn", "")))),
                    ft.DataCell(ft.Text(str(item.get("da", "")))),
                    ft.DataCell(ft.Text(str(item.get("size", "")))),
                    ft.DataCell(ft.Text(f"{price:.2f}")),
                    ft.DataCell(ft.Text(str(quantity))),
                    ft.DataCell(ft.Text(f"€{zwischensumme:.2f}")),
                    ft.DataCell(ft.IconButton(ft.icons.DELETE, on_click=lambda _, i=index: self.remove_item(i))),
                ]
            )
            self.items_container.rows.append(row)
        
        self.update_total()
        if self.page:
            self.page.update()

    def rechnung_aktualisieren(self, rechnung_id):
        # Similar to rechnung_absenden, but update existing invoice
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()
            return
        
        client_email = self.client_email_dropdown.value if self.client_email_dropdown.value != "Neue E-Mail" else self.client_email_entry.value
        
        invoice_date = datetime.now().strftime("%Y-%m-%d")
        total = sum(float(item["price"].value) * int(item["quantity"].value) for item in self.items)
        
        invoice_items = [
            {
                "description": item["description"].value,
                "dn": item["dn"].value,
                "da": item["da"].value,
                "size": item["size"].value,
                "price": float(item["price"].value),
                "quantity": int(item["quantity"].value)
            }
            for item in self.items
        ]
        
        invoice_data = {
            "id": rechnung_id,
            "client_name": self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value,
            "client_email": client_email,
            "invoice_date": invoice_date,
            "total": total,
            "items": invoice_items
        }
        
        if self.update_rechnung(invoice_data):
            pdf_path = self.pdf_generieren(invoice_data)
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Rechnung erfolgreich aktualisiert und gespeichert als: {pdf_path}"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.reset_form()
            self.rechnungen_anzeigen(None)  # Refresh the invoice list
        else:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Fehler beim Aktualisieren der Rechnung"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
        self.page.update()

    def update_rechnung(self, invoice_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE invoices
                SET client_name = ?, client_email = ?, invoice_date = ?, total = ?
                WHERE id = ?
            ''', (invoice_data['client_name'], invoice_data['client_email'], invoice_data['invoice_date'], invoice_data['total'], invoice_data['id']))

            cursor.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (invoice_data['id'],))

            for item in invoice_data['items']:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_data['id'], item['description'], item['dn'], item['da'], item['size'], item['price'], item['quantity']))

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def rechnungen_abrufen(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT i.id, i.client_name, i.bestell_nr, i.bestelldatum, i.baustelle, i.anlagenteil,
                       i.aufmass_nr, i.aufmassart, i.auftrags_nr, i.ausfuehrungsbeginn, i.ausfuehrungsende,
                       i.total, COUNT(ii.id) as item_count
                FROM invoices i
                LEFT JOIN invoice_items ii ON i.id = ii                GROUP BY i.id
                ORDER BY i.id DESC
            ''')
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def update_client_dropdowns(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch unique client names
        cursor.execute('SELECT DISTINCT client_name FROM invoices ORDER BY client_name')
        client_names = [row[0] for row in cursor.fetchall()]
        self.client_name_dropdown.options = [ft.dropdown.Option(name) for name in client_names] + [ft.dropdown.Option("Neuer Kunde")]
        
        # Fetch unique client emails
        cursor.execute('SELECT DISTINCT client_email FROM invoices ORDER BY client_email')
        client_emails = [row[0] for row in cursor.fetchall()]
        self.client_email_dropdown.options = [ft.dropdown.Option(email) for email in client_emails] + [ft.dropdown.Option("Neue E-Mail")]
        
        conn.close()

        # Reset dropdown values and hide entry fields
        self.client_name_dropdown.value = None
        self.client_email_dropdown.value = None
        self.client_name_entry.visible = False
        self.client_email_entry.visible = False

        # Update the UI
        self.page.update()
   
   
    def show_snackbar(self, message):
        if self.page:
            snack_bar = ft.SnackBar(content=ft.Text(message))
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()
        else:
            print(f"Snackbar message (page not available): {message}")


    def handle_duplicate_check(self):
        # Check if there are any duplicate items in the invoice
        seen_items = set()
        for item in self.items:
            item_key = (
                item["description"].value,
                item["dn"].value,
                item["da"].value,
                item["size"].value,
                item["price"].value,
                item["taetigkeit"].value
            )
            if item_key in seen_items:
                self.show_snackbar("Duplikate gefunden. Bitte überprüfen Sie die Einträge.")
                return True
            seen_items.add(item_key)
        return False

    def rechnung_loeschen(self, rechnung_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            print(f"Attempting to delete invoice with ID: {rechnung_id}")
            cursor.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (rechnung_id,))
            cursor.execute('DELETE FROM invoices WHERE id = ?', (rechnung_id,))
            conn.commit()
            print(f"Invoice {rechnung_id} deleted successfully")
            return True
        except sqlite3.Error as e:
            print(f"An error occurred while deleting invoice {rechnung_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def find_existing_item(self, new_item):
        for item in self.items:
            if (item["description"].value == new_item["description"].value and
                item["dn"].value == new_item["dn"].value and
                item["da"].value == new_item["da"].value and
                item["size"].value == new_item["size"].value and
                item["price"].value == new_item["price"].value):
                return item
        return None
        return None
        return None
        return None
        return None
        return None
        return None
        return None

    def update_item_subtotal(self, item):
        price = float(item["price"].value) if item["price"].value else 0
        quantity = float(item["quantity"].value) if item["quantity"].value else 0
        taetigkeit = item["taetigkeit"].value if "taetigkeit" in item else ""

        factor = self.get_ausfuehrung_factor(taetigkeit)

        subtotal = price * quantity * factor
        item["zwischensumme"].value = f"{subtotal:.2f}"
        
        print(f"Updating zwischensumme: Price: {price}, Quantity: {quantity}, Tätigkeit: {taetigkeit}, Factor: {factor}, Zwischensumme: {subtotal}")
        
        if item["zwischensumme"].page:
            item["zwischensumme"].update()
        
        # Aktualisiere den Gesamtpreis
        self.update_gesamtpreis()

    def get_ausfuehrung_factor(self, taetigkeit):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Faktor FROM Ausfuehrung WHERE Taetigkeit = ?', (taetigkeit,))
            result = cursor.fetchone()
            factor = float(result[0]) if result else 1.0
            print(f"Ausfuehrung factor for {taetigkeit}: {factor}")  # Debugging-Ausgabe
            return factor
        finally:
            conn.close()

    def update_gesamtpreis(self):
        gesamtpreis = sum(float(item["zwischensumme"].value) for item in self.items if item["zwischensumme"].value)
        self.gesamtpreis_text.value = f"Gesamtpreis: €{gesamtpreis:.2f}"
        if self.page:
            self.page.update()

    def get_unique_bauteil_values(self):
        db_path = get_db_path()
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
        
            # Get regular Bauteil values
            cursor.execute('SELECT DISTINCT bauteil FROM price_list ORDER BY bauteil')
            bauteil_values = [row[0] for row in cursor.fetchall()]
        
            # Get Formteil values
            cursor.execute('SELECT Formteilbezeichnung FROM Formteile ORDER BY Position')
            formteil_values = [row[0] for row in cursor.fetchall()]
        
            # Combine regular Bauteil values and Formteile with a heading
            return bauteil_values + ["Formteile"] + formteil_values
        except sqlite3.Error as e:
            print(f"Fehler beim Abrufen der Bauteil-Werte: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def show_main_view(self, e):
        # Clear the current page content
        self.page.controls.clear()
        
        # Rebuild the main UI
        main_view = self.build_ui()
        
        # Add the main view back to the page
        self.page.add(main_view)
        
        # Update the page to reflect changes
        self.page.update()

    # ... rest of the class ...
        
        # ... (rest of the update_rechnung implementation)

def main(page: ft.Page):
    app = InvoicingApp(page)
    page.add(app)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)