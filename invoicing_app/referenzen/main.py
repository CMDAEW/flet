# -*- coding: utf-8 -*-
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
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from cmath import e
from httpx import options
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
            CREATE TABLE IF NOT EXISTS Taetigkeiten (
                Position INTEGER PRIMARY KEY,
                Taetigkeit TEXT NOT NULL,
                Faktor REAL NOT NULL
            )
        ''')
        
        # Create Sonstige Zuschläge table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Zuschlaege (
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
            csv_path = resource_path('EP.csv')
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
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()
        self.items = []
        self.initialize_ui_elements()
        self.taetigkeit_options = self.get_taetigkeit_options()

    def initialize_ui_elements(self):
        # Kundeninformationen
        self.client_name_dropdown = ft.Dropdown(label="Kundenname", width=300)
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", visible=False)
        self.client_email_dropdown = ft.Dropdown(label="Kunden-E-Mail", width=300)
        self.client_email_entry = ft.TextField(label="Neue E-Mail", visible=False)
        
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
        
        self.gesamtpreis_text = ft.Text("Gesamtpreis: €0.00", size=20)
        self.total_field = ft.TextField(label="Gesamtsumme", read_only=True)

    def build(self):
        return ft.Column([
            ft.Row([self.client_name_dropdown, self.client_email_dropdown]),
            ft.Row([self.client_name_entry, self.client_email_entry]),
            ft.Row([self.bestell_nr, self.bestelldatum, self.baustelle]),
            ft.Row([self.anlagenteil, self.aufmass_nr, self.aufmassart]),
            ft.Row([self.auftrags_nr, self.ausfuehrungsbeginn, self.ausfuehrungsende]),
            self.items_container,
            ft.Row([
                ft.ElevatedButton("Position hinzufügen", on_click=self.add_item),
                ft.ElevatedButton("Rechnung speichern", on_click=self.save_invoice),
                ft.ElevatedButton("PDF generieren", on_click=self.generate_pdf)
            ]),
            self.gesamtpreis_text,
            self.total_field
        ])

    def add_item(self, e=None):
        new_item = {
            "taetigkeit": ft.Dropdown(
                label="Tätigkeit",
                options=[ft.dropdown.Option(t) for t in self.taetigkeit_options],
                width=200,
                on_change=self.on_taetigkeit_change
            ),
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                options=[ft.dropdown.Option(b) for b in self.get_unique_bauteil_values()],
                width=200,
                on_change=self.on_description_change
            ),
            "dn": ft.Dropdown(label="DN", width=100, visible=False, on_change=self.on_dn_change),
            "da": ft.Dropdown(label="DA", width=100, visible=False, on_change=self.on_da_change),
            "size": ft.Dropdown(label="Dämmdicke", width=100, visible=False, on_change=self.on_size_change),
            "price": ft.TextField(label="Einheitspreis", width=100, read_only=True),
            "quantity": ft.TextField(label="Menge", width=100, on_change=self.on_quantity_change),
            "zwischensumme": ft.TextField(label="Zwischensumme", width=100, read_only=True),
            "remove_button": ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                tooltip="Entfernen",
                on_click=lambda _: self.remove_item(new_item)
            )
        }
        
        for control in new_item.values():
            if isinstance(control, ft.Control):
                control.data = new_item

        self.items.append(new_item)
        self.update_items_ui()
        self.update_item_options(new_item, "description")

    def on_taetigkeit_change(self, e):
        item = e.control.data
        self.update_item_subtotal(item)

    def on_description_change(self, e):
        item = e.control.data
        self.update_item_options(item, "description")

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

    def remove_item(self, item):
        self.items.remove(item)
        self.update_items_ui()

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
        
        self.update_gesamtpreis()

    def update_gesamtpreis(self):
        gesamtpreis = sum(float(item["zwischensumme"].value) for item in self.items if item["zwischensumme"].value)
        self.gesamtpreis_text.value = f"Gesamtpreis: €{gesamtpreis:.2f}"
        if self.page:
            self.page.update()

    def get_unique_bauteil_values(self):
        conn = self.conn
        cursor = conn.cursor()
        try:
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
            cursor.close()

    def get_taetigkeit_options(self):
        conn = self.conn
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Taetigkeit FROM Ausfuehrung ORDER BY Position')
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

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

    def save_invoice(self, e):
        if not self.client_name_dropdown.value or not self.items:
            self.show_snackbar("Bitte füllen Sie alle erforderlichen Felder aus.")
            return
        
        invoice_data = {
            "client_name": self.client_name_dropdown.value,
            "bestell_nr": self.bestell_nr.value,
            "bestelldatum": self.bestelldatum.value,
            "baustelle": self.baustelle.value,
            "anlagenteil": self.anlagenteil.value,
            "aufmass_nr": self.aufmass_nr.value,
            "aufmassart": self.aufmassart.value,
            "auftrags_nr": self.auftrags_nr.value,
            "ausfuehrungsbeginn": self.ausfuehrungsbeginn.value,
            "ausfuehrungsende": self.ausfuehrungsende.value,
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

        if self.save_invoice_to_db(invoice_data):
            self.show_snackbar("Rechnung erfolgreich gespeichert.")
            self.reset_form()
        else:
            self.show_snackbar("Fehler beim Speichern der Rechnung.")

    def generate_pdf(self, e):
        if not self.client_name_dropdown.value or not self.items:
            self.show_snackbar("Bitte füllen Sie alle erforderlichen Felder aus und fügen Sie mindestens einen Artikel hinzu.")
            return
        
        invoice_data = self.collect_invoice_data()
        pdf_path = self.pdf_generieren(invoice_data)
        self.show_snackbar(f"PDF wurde generiert: {pdf_path}")

    def show_snackbar(self, message):
        if self.page:
            snack_bar = ft.SnackBar(content=ft.Text(message))
            self.page.snack_bar = snack_bar
            snack_bar.open = True
            self.page.update()
        else:
            print(f"Snackbar message (page not available): {message}")

    # Zusätzliche Hilfsmethoden

    def get_available_options(self, bauteil):
        conn = self.conn
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
            cursor.close()

    def get_da_options(self, bauteil, dn):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY da', ('Rohrleitung', dn))
            else:
                cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY da', (bauteil, dn))
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_size_options(self, bauteil, dn, da):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
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
            cursor.close()

    def is_formteil(self, bauteil):
        conn = self.conn
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def get_ausfuehrung_factor(self, taetigkeit):
        conn = self.conn
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Faktor FROM Ausfuehrung WHERE Taetigkeit = ?', (taetigkeit,))
            result = cursor.fetchone()
            factor = float(result[0]) if result else 1.0
            print(f"Ausfuehrung factor for {taetigkeit}: {factor}")  # Debugging-Ausgabe
            return factor
        finally:
            cursor.close()

    def update_price(self, item):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        price = self.get_price(bauteil, dn, da, size)
        item["price"].value = f"{price:.2f}"
        self.update_item_subtotal(item)

    def get_price(self, bauteil, dn, da, size):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                cursor.execute('SELECT Faktor FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
                formteil_faktor = cursor.fetchone()
                if formteil_faktor:
                    cursor.execute('''
                        SELECT value FROM price_list 
                        WHERE bauteil = 'Rohrleitung' AND dn = ? AND da = ? AND size = ?
                    ''', (dn, da, size))
                    base_price = cursor.fetchone()
                    if base_price:
                        return base_price[0] * formteil_faktor[0]
            else:
                cursor.execute('''
                    SELECT value FROM price_list 
                    WHERE bauteil = ? AND dn = ? AND da = ? AND size = ?
                ''', (bauteil, dn, da, size))
                price = cursor.fetchone()
                if price:
                    return price[0]
            return 0
        finally:
            cursor.close()

    def calculate_total(self):
        return sum(float(item["zwischensumme"].value) for item in self.items if item["zwischensumme"].value)

    def reset_form(self):
        # Implementieren Sie hier die Logik zum Zurücksetzen des Formulars
        pass

    def save_invoice_to_db(self, invoice_data):
        conn = self.conn
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoices (client_name, bestell_nr, bestelldatum, baustelle, anlagenteil, aufmass_nr, aufmassart, auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data["client_name"],
                invoice_data["bestell_nr"],
                invoice_data["bestelldatum"],
                invoice_data["baustelle"],
                invoice_data["anlagenteil"],
                invoice_data["aufmass_nr"],
                invoice_data["aufmassart"],
                invoice_data["auftrags_nr"],
                invoice_data["ausfuehrungsbeginn"],
                invoice_data["ausfuehrungsende"],
                invoice_data["total"]
            ))
            invoice_id = cursor.lastrowid
            
            for item in invoice_data["items"]:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity, taetigkeit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id,
                    item["description"],
                    item["dn"],
                    item["da"],
                    item["size"],
                    item["price"],
                    item["quantity"],
                    item["taetigkeit"]
                ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Fehler beim Speichern der Rechnung: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

    def collect_invoice_data(self):
        # Implementieren Sie die Logik zum Sammeln der Rechnungsdaten
        pass

    def pdf_generieren(self, invoice_data):
        # Implementieren Sie die Logik zum Generieren des PDFs
        pass

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)