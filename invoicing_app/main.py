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
                client_email TEXT,
                invoice_date TEXT,
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
                csvreader = csv.reader(csvfile)
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
                                float(row[5]) if row[5] else None,
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

def save_invoice(self, invoice_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoices (client_name, client_email, invoice_date, total)
                VALUES (?, ?, ?, ?)
            ''', (invoice_data['client_name'], invoice_data['client_email'], invoice_data['invoice_date'], 0))  # Set total to 0 for now

            invoice_id = cursor.lastrowid  # Get the last inserted invoice ID

            for item in invoice_data['items']:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity, taetigkeit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, item['description'], item['dn'], item['da'], item['size'], item['price'], item['quantity'], item['taetigkeit']))

            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

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
        # Keine Artikelzeilen hier hinzufügen

    def build_ui(self):
        bauteil_values = self.get_unique_bauteil_values()
        customer_names = self.get_unique_client_names()
        customer_emails = self.get_unique_customer_emails()

        # Add corporate identity logo with increased size
        logo_path = resource_path("Assets/KAE_Logo_RGB_300dpi.jpg")
        if os.path.exists(logo_path):
            logo = ft.Image(src=logo_path, width=600, height=200)  # Increased logo size
            header = ft.Row([ft.Text("Rechnungs-App", size=30), logo], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        else:
            header = ft.Text("Rechnungs-App", size=30)

        # Add the header to your layout
        self.page.add(header)

        self.client_name_dropdown = ft.Dropdown(
            label="Kundenname",
            width=300,
            options=[ft.dropdown.Option("Neuer Kunde")] + [ft.dropdown.Option(name) for name in customer_names],
            on_change=lambda _: self.toggle_name_entry()
        )
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", width=300, visible=False, adaptive=True)

        self.client_email_dropdown = ft.Dropdown(
            label="Kunden-E-Mail",
            width=300,
            options=[ft.dropdown.Option("Neue E-Mail")] + [ft.dropdown.Option(email) for email in customer_emails],
            on_change=lambda _: self.toggle_email_entry()
        )
        self.client_email_entry = ft.TextField(label="Neue Kunden-E-Mail", width=300, visible=False, adaptive=True)

        self.submit_invoice_button = ft.ElevatedButton("Aufmass erstellen", on_click=self.Aufmass_erstellen)
        self.generate_invoice_without_prices_button = ft.ElevatedButton("Rechnung ohne Preise generieren", on_click=self.rechnung_ohne_preise_generieren)
        self.show_existing_invoices_button = ft.ElevatedButton("Vorhandene Rechnungen", on_click=self.rechnungen_anzeigen)
        add_item_button = ft.ElevatedButton("Artikel hinzufügen", on_click=lambda _: self.add_item(), adaptive=True)
        
        main_column = ft.Column([
            self.client_name_dropdown,
            self.client_name_entry,
            self.client_email_dropdown,
            self.client_email_entry,
            add_item_button,
            self.items_container,
            self.gesamtpreis_text,
            ft.Row([self.submit_invoice_button, self.generate_invoice_without_prices_button, self.show_existing_invoices_button])
        ], scroll=ft.ScrollMode.ALWAYS)

        scrollable_view = ft.Row(
            [main_column],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
        )

        return scrollable_view
    
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

    def update_item_options(self, item, changed_field):
        if changed_field == "description":
            bauteil = item["description"].value
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
            
            # Only update if the control is already on the page
            if item["dn"].page:
                item["dn"].update()
            if item["da"].page:
                item["da"].update()
            if item["size"].page:
                item["size"].update()
        
        self.update_price(item)

    def update_price(self, item):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        
        price = self.get_price(bauteil, dn, da, size)
        
        if price is not None:
            item["price"].value = f"{price:.2f}"
            print(f"Updating price: {price:.2f}")  # Debugging-Ausgabe
            if item["price"].page:
                item["price"].update()
        else:
            print(f"Price not found for: {bauteil}, DN: {dn}, DA: {da}, Size: {size}")
        
        self.update_item_subtotal(item)

    def update_item_subtotal(self, item):
        price = float(item["price"].value) if item["price"].value else 0
        quantity = int(item["quantity"].value) if item["quantity"].value else 0
        taetigkeit = item["taetigkeit"].value

        factor = self.get_ausfuehrung_factor(taetigkeit)

        subtotal = price * quantity * factor
        item["zwischensumme"].value = f"{subtotal:.2f}"
        
        print(f"Updating zwischensumme: Price: {price}, Quantity: {quantity}, Factor: {factor}, Zwischensumme: {subtotal}")
        
        self.update_gesamtpreis()
        self.page.update()

    def get_formteil_factor(self, formteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Faktor FROM Formteile WHERE Formteilbezeichnung = ?', (formteil,))
            result = cursor.fetchone()
            return float(result[0]) if result else None
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

    def rechnung_ohne_preise_generieren(self, e):
        if self.handle_duplicate_check():
            return
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            self.show_snackbar("Bitte füllen Sie alle Felder aus")
            return
        
        client_name = self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value
        client_email = self.client_email_dropdown.value if self.client_email_dropdown.value != "Neue E-Mail" else self.client_email_entry.value
        
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
            "client_email": client_email,
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
        # ... (restlicher Code)

    def pdf_generieren_ohne_preise(self, rechnungsdaten):
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
        doc = SimpleDocTemplate(pdf_path, pagesize=landscape)
        elements = []

        # Add invoice details
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Rechnung für: {rechnungsdaten['client_name']}", styles['Heading1']))
        elements.append(Paragraph(f"E-Mail: {rechnungsdaten['client_email']}", styles['Normal']))
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

    # ... (rest of the class methods)

    def main(self, page: ft.Page):
        self.page = page
        self.page.title = "Rechnungserstellung"
        self.page.window_width = 1600  # Increased width further
        self.page.window_height = 800
        self.page.window_resizable = True
        self.page.padding = 20
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.fonts = {
            "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
        }
        self.page.theme = ft.Theme(font_family="Roboto")
        self.page.adaptive = True

        self.submit_invoice_button = ft.ElevatedButton("Aufmass erstellen", on_click=self.Aufmass_erstellen)
        self.update_invoice_button = ft.ElevatedButton("Rechnung aktualisieren", visible=False)

        # Build the UI and add it to the page
        main_view = self.build_ui()
        self.page.add(main_view)

        self.page.on_route_change = self.route_change
        self.page.go('/')

        self.add_item()  # Add an empty item line on initial load
        self.page.update()

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
        if self.handle_duplicate_check():
            return
        rechnungen = self.rechnungen_abrufen()
        rechnungsliste = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Kunde"), numeric=False),
                ft.DataColumn(ft.Text("Datum"), numeric=False),
                ft.DataColumn(ft.Text("Gesamt"), numeric=True),
                ft.DataColumn(ft.Text("Aktionen"), numeric=False),
            ],
            rows=[],
            column_spacing=50,
            horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
        )
        
        for rechnung in rechnungen:
            rechnungsliste.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(rechnung[1])),  # Kundenname
                        ft.DataCell(ft.Text(rechnung[3])),  # Datum
                        ft.DataCell(ft.Text(f"€{rechnung[4]:.2f}")),  # Gesamt
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    tooltip="Rechnung bearbeiten",
                                    on_click=lambda _, id=rechnung[0]: self.rechnung_bearbeiten(id)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.PICTURE_AS_PDF,
                                    tooltip="PDF neu generieren",
                                    on_click=lambda _, id=rechnung[0]: self.pdf_neu_generieren_und_anzeigen(id)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    tooltip="Rechnung löschen",
                                    on_click=lambda _, id=rechnung[0]: self.rechnung_loeschen_bestaetigen(id)
                                )
                            ])
                        )
                    ]
                )
            )
        
        def close_dialog(dialog):
            dialog.open = False
            self.page.update()

        rechnungs_dialog = ft.AlertDialog(
            title=ft.Text("Vorhandene Rechnungen"),
            content=ft.Container(
                content=ft.ListView(controls=[rechnungsliste], expand=1, spacing=10, padding=20, auto_scroll=True),
                width=800,
                height=500,
            ),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: close_dialog(rechnungs_dialog))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.overlay.append(rechnungs_dialog)
        rechnungs_dialog.open = True
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
        pdf_path = os.path.join(os.path.expanduser("~"), "Downloads", pdf_dateiname)
        
        # Verwenden Sie A4 im Querformat
        doc = SimpleDocTemplate(pdf_path, pagesize=landscape(A4))
        elements = []
        
        # Verbesserte Stile
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', alignment=1))
        styles.add(ParagraphStyle(name='Right', alignment=2))
        
        # Firmenlogo (wenn vorhanden)
        logo_path = resource_path("Assets/KAE_Logo_RGB_300dpi2.png")
        if os.path.exists(logo_path):
            logo = Image(logo_path)
            logo.drawHeight = 1*inch
            logo.drawWidth = 1*inch
            elements.append(logo)
        
        # Rechnungsdetails
        elements.append(Paragraph(f"Rechnung für: {rechnungsdaten['client_name']}", styles['Heading1']))
        elements.append(Paragraph(f"E-Mail: {rechnungsdaten['client_email']}", styles['Normal']))
        elements.append(Paragraph(f"Datum: {rechnungsdaten['invoice_date']}", styles['Normal']))
        elements.append(Spacer(1, 0.25*inch))
        
        # Tabelle für Rechnungspositionen
        data = [['Tätigkeit', 'Beschreibung', 'DN', 'DA', 'Größe', 'Preis', 'Menge', 'Zwischensumme']]
        for item in rechnungsdaten['items']:
            row = [
                item.get('taetigkeit', ''),  # Make sure 'taetigkeit' is included here
                item['description'],
                item.get('dn', ''),
                item.get('da', ''),
                item['size'],
                f"€{item['price']:.2f}",
                str(item['quantity']),
                f"€{float(item['price']) * float(item['quantity']):.2f}"
            ]
            data.append(row)
        
        # Gesamtbetrag
        data.append(['', '', '', '', '', '', 'Gesamtbetrag:', f"€{rechnungsdaten['total']:.2f}"])
        
        # Erstellen Sie die Tabelle mit angepassten Spaltenbreiten
        col_widths = [6*cm, 4*cm, 1.5*cm, 1.5*cm, 2*cm, 2*cm, 1.5*cm, 3.5*cm]  # Tätigkeitsfeld und Zwischensumme breiter gemacht
        table = Table(data, colWidths=col_widths)
        
        # Tabellenstil
        table_style = TableStyle([
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
        table.setStyle(table_style)
        
        elements.append(table)
        
        # Fügen Sie Fußzeile hinzu
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("Vielen Dank für Ihr Geschäft!", styles['Center']))
        
        # Generieren Sie das PDF
        doc.build(elements)
        
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
        taetigkeit_value = item.get("taetigkeit", "") if item else ""
        description_value = item.get("description", "") if item else ""
        dn_value = item.get("dn", "") if item else ""
        da_value = item.get("da", "") if item else ""
        size_value = item.get("size", "") if item else ""
        price_value = str(item.get("price", "")) if item else ""
        quantity_value = str(item.get("quantity", "1")) if item else "1"

        new_item = {
            "taetigkeit": ft.Dropdown(
                label="Tätigkeit",
                width=300,
                options=[ft.dropdown.Option(t) for t in self.taetigkeit_options],
                value=taetigkeit_value,
                on_change=lambda _: self.update_item_options(new_item, "taetigkeit")
            ),
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                width=300,
                options=[ft.dropdown.Option(b) for b in self.get_unique_bauteil_values()],
                value=description_value,
                on_change=lambda _: self.update_item_options(new_item, "description")
            ),
            "dn": ft.Dropdown(
                label="DN",
                width=150,
                visible=False,
                value=dn_value,
                on_change=lambda _: self.update_item_options(new_item, "dn")
            ),
            "da": ft.Dropdown(
                label="DA",
                width=150,
                visible=False,
                value=da_value,
                on_change=lambda _: self.update_item_options(new_item, "da")
            ),
            "size": ft.Dropdown(
                label="Dämmdicke",
                width=150,
                value=size_value,
                on_change=lambda _: self.update_item_options(new_item, "size")
            ),
            "price": ft.TextField(
                label="Einheitspreis",
                width=100,
                value=price_value,
                read_only=True
            ),
            "quantity": ft.TextField(
                label="Menge",
                width=50,
                value=quantity_value,
                on_change=lambda _: self.update_item_subtotal(new_item)
            ),
            "zwischensumme": ft.TextField(
                label="Zwischensumme",
                width=100,
                read_only=True
            ),
            "remove_button": ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                on_click=lambda _: self.remove_item(new_item)
            )
        }

        self.items.append(new_item)
        self.items_container.controls.append(ft.Row(controls=[
            new_item["taetigkeit"],
            new_item["description"],
            new_item["dn"],
            new_item["da"],
            new_item["size"],
            new_item["price"],
            new_item["quantity"],
            new_item["zwischensumme"],
            new_item["remove_button"]
        ]))

        self.update_item_options(new_item, "description")
        self.update_item_subtotal(new_item)
        self.page.update()

        return new_item

    def get_taetigkeit_options(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Taetigkeit FROM Ausfuehrung ORDER BY Position')
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

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

    def update_item_options(self, item, changed_field):
        selected_taetigkeit = item["taetigkeit"].value
        print(f"Ausgewählte Tätigkeit: {selected_taetigkeit}")  # Debugging-Ausgabe
        selected_description = item["description"].value
        selected_dn = item["dn"].value
        selected_da = item["da"].value
        selected_size = item["size"].value

        # Check if the selected item is a Formteil
        is_formteil = self.is_formteil(selected_description)

        if selected_description:
            available_options = self.get_available_options(selected_description)
            print(f"Available options: {available_options}")

            # Update DN and DA options with available values
            dn_options = sorted(set(dn for dn, _, _ in available_options if dn != 0 and dn is not None))
            da_options = sorted(set(da for _, da, _ in available_options if da != 0 and da is not None))
            
            # Always show DN and DA fields for Formteile, otherwise show when they are not null
            item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
            item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
            item["dn"].visible = is_formteil or bool(dn_options)
            item["da"].visible = is_formteil or bool(da_options)

            # Set the label of DN dropdown to an empty string
            item["dn"].label = ""

            print(f"DN options: {dn_options}")
            print(f"DA options: {da_options}")

            if changed_field == "description":
                # Reset DN and DA values
                item["dn"].value = f"{dn_options[0]:.0f}" if dn_options and float(dn_options[0]).is_integer() else f"{dn_options[0]}" if dn_options else None
                item["da"].value = f"{da_options[0]:.1f}" if da_options else None
            
            elif changed_field in ["dn", "da"]:
                # Update the other dimension based on the selected one
                if changed_field == "dn" and selected_dn:
                    matching_da = sorted(set(da for dn, da, _ in available_options if dn == float(selected_dn) and da != 0 and da is not None))
                    item["da"].value = f"{matching_da[0]:.1f}" if matching_da else None
                elif changed_field == "da" and selected_da:
                    matching_dn = sorted(set(dn for dn, da, _ in available_options if da == float(selected_da) and dn != 0 and dn is not None))
                    item["dn"].value = f"{matching_dn[0]:.0f}" if matching_dn and float(matching_dn[0]).is_integer() else f"{matching_dn[0]}" if matching_dn else None

            # Update size options based on current DN and DA selection
            selected_dn = item["dn"].value
            selected_da = item["da"].value
            
            if selected_dn and selected_da:
                matching_size = sorted(set(size for dn, da, size in available_options 
                                           if dn == float(selected_dn) and da == float(selected_da)),
                                       key=lambda x: float(x.split('-')[0].strip().rstrip('mm')))
            else:
                # If DN or DA is not selected, show all available sizes for the Bauteil
                matching_size = sorted(set(size for _, _, size in available_options),
                                       key=lambda x: float(x.split('-')[0].strip().rstrip('mm')))

            print(f"Matching sizes: {matching_size}")

            item["size"].options = [ft.dropdown.Option(value) for value in matching_size]
            if selected_size in matching_size:
                item["size"].value = selected_size
            elif matching_size:
                item["size"].value = matching_size[0]
            item["size"].visible = True

        # Update the dropdowns
        if item["dn"].page:
            item["dn"].update()
        if item["da"].page:
            item["da"].update()
        if item["size"].page:
            item["size"].update()
        
        # Update the price and subtotal
        self.update_price(item)
        self.update_item_subtotal(item)
        self.update_gesamtpreis()
        self.page.update()

        print(f"Final values - DN: {item['dn'].value}, DA: {item['da'].value}, Size: {item['size'].value}")

    def is_formteil(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def pdf_neu_generieren_und_anzeigen(self, rechnung_id):
        result = self.pdf_neu_generieren(rechnung_id)
        self.page.snack_bar = ft.SnackBar(content=ft.Text(result))
        self.page.overlay.append(self.page.snack_bar)
        self.page.snack_bar.open = True
        self.page.update()

    def pdf_neu_generieren(self, rechnung_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch invoice details
        cursor.execute('SELECT * FROM invoices WHERE id = ?', (rechnung_id,))
        invoice = cursor.fetchone()
        
        # Fetch invoice items
        cursor.execute('SELECT * FROM invoice_items WHERE invoice_id = ?', (rechnung_id,))
        items = cursor.fetchall()
        
        conn.close()
        
        if invoice:
            rechnungsdaten = {
                'client_name': invoice[1],
                'client_email': invoice[2],
                'invoice_date': invoice[3],
                'total': invoice[4],
                'items': [
                    {
                        'description': item[2],
                        'dn': item[3],
                        'da': item[4],
                        'size': item[5],
                        'price': item[6],
                        'quantity': item[7],
                        'taetigkeit': item[8]  # Ensure 'taetigkeit' is included
                    } for item in items
                ]
            }
            
            pdf_dateiname = self.pdf_generieren(rechnungsdaten)
            return f"PDF neu generiert: {pdf_dateiname}"
        else:
            return "Rechnung nicht gefunden"

    def rechnung_loeschen_bestaetigen(self, rechnung_id):
        def delete_confirmed(e):
            if self.rechnung_loeschen(rechnung_id):
                self.show_snackbar("Rechnung erfolgreich gelöscht")
                self.page.dialog.open = False
                self.rechnungen_anzeigen(None)  # Refresh the invoice list
            else:
                self.show_snackbar("Fehler beim Löschen der Rechnung")
            self.page.update()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rechnung löschen"),
            content=ft.Text(f"Sind Sie sicher, dass Sie die Rechnung {rechnung_id} löschen möchten?"),
            actions=[
                ft.TextButton("Abbrechen", on_click=lambda _: self.close_dialog(confirm_dialog)),
                ft.TextButton("Löschen", on_click=delete_confirmed),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = confirm_dialog
        confirm_dialog.open = True
        self.page.update()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rechnung löschen"),
            content=ft.Text(f"Sind Sie sicher, dass Sie die Rechnung {rechnung_id} löschen möchten?"),
            actions=[
                ft.TextButton("Abbrechen", on_click=lambda _: self.close_dialog(confirm_dialog)),
                ft.TextButton("Löschen", on_click=delete_confirmed),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = confirm_dialog
        confirm_dialog.open = True
        self.page.update()

    def close_dialog(self, dialog):
        dialog.open = False
        self.page.update()

    def update_gesamtpreis(self):
        gesamtpreis = sum(float(item["subtotal"].value) for item in self.items if item["subtotal"].value)
        self.gesamtpreis_text.value = f"Gesamtpreis: €{gesamtpreis:.2f}"
        self.page.update()

    def add_item(self):
        bauteil_values = self.get_unique_bauteil_values()
        taetigkeit_options = self.get_taetigkeit_options()
        
        new_item = {
            "taetigkeit": ft.Dropdown(
                label="Tätigkeit",
                width=300,
                options=[ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeit_options],
                on_change=lambda _: self.update_item_subtotal(new_item)
            ),
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                width=300,
                options=[ft.dropdown.Option(b, disabled=(b == "Formteile")) for b in bauteil_values],
                on_change=lambda _: self.update_item_options(new_item, "description")
            ),
            "dn": ft.Dropdown(
                label="DN",
                width=150,
                visible=False
            ),
            "da": ft.Dropdown(
                label="DA",
                width=150,
                visible=False
            ),
            "size": ft.Dropdown(
                label="Dämmdicke",
                width=150
            ),
            "price": ft.TextField(
                label="Einheitspreis",
                value="0.00",
                width=100,
                read_only=True
            ),
            "quantity": ft.TextField(
                label="Menge",
                width=50,
                value="1",
                on_change=lambda _: self.update_item_subtotal(new_item)
            ),
            "zwischensumme": ft.TextField(
                label="Zwischensumme",
                value="0.00",
                width=100,
                read_only=True
            ),
            "remove_button": ft.IconButton(
                icon=ft.icons.DELETE_OUTLINE,
                tooltip="Entfernen",
                on_click=lambda _, idx=len(self.items): self.remove_item(idx)
            ),
        }

        self.items.append(new_item)
        self.rebuild_items_container()

        # Set up event handlers after the item has been added to the page
        new_item["taetigkeit"].on_change = lambda e: self.update_item_options(new_item, "taetigkeit")
        new_item["description"].on_change = lambda e: self.update_item_options(new_item, "description")
        new_item["dn"].on_change = lambda e: self.update_item_options(new_item, "dn")
        new_item["da"].on_change = lambda e: self.update_item_options(new_item, "da")
        new_item["size"].on_change = lambda e: self.update_item_options(new_item, "size")

        self.update_gesamtpreis()
        self.page.update()

    def update_item_subtotal(self, item):
        price = float(item["price"].value) if item["price"].value else 0
        quantity = int(item["quantity"].value) if item["quantity"].value else 0
        taetigkeit = item["taetigkeit"].value

        factor = self.get_ausfuehrung_factor(taetigkeit)

        subtotal = price * quantity * factor
        item["zwischensumme"].value = f"{subtotal:.2f}"
        
        print(f"Updating zwischensumme: Price: {price}, Quantity: {quantity}, Factor: {factor}, Zwischensumme: {subtotal}")
        
        self.update_gesamtpreis()
        self.page.update()

    def update_gesamtpreis(self):
        gesamtpreis = sum(float(item["zwischensumme"].value) for item in self.items if item["zwischensumme"].value)
        self.gesamtpreis_text.value = f"Gesamtpreis: €{gesamtpreis:.2f}"
        self.page.update()

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
            self.update_gesamtpreis()
            self.page.update()
        else:
            print(f"Item not found in the list: {item}")

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
            self.update_gesamtpreis()
            self.page.update()
        else:
            print(f"Item not found in the list: {item}")

    # Remove the create_remove_handler and remove_item_by_index methods

    def create_remove_handler(self, index):
        return lambda _: self.remove_item_by_index(index)

    def remove_item_by_index(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            # Update the remove_button for all remaining items
            for i, item in enumerate(self.items):
                item["remove_button"].on_click = self.create_remove_handler(i)
            self.update_gesamtpreis()
            self.page.update()
        else:
            print(f"Invalid index: {index}")

    def get_price(self, bauteil, dn, da, size):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # First, check if it's a Formteil
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            is_formteil = cursor.fetchone() is not None
            
            if is_formteil:
                # For Formteile, we need to find the corresponding Rohrleitung price
                if dn is not None and da is not None:
                    cursor.execute('''
                        SELECT value FROM price_list
                        WHERE bauteil = 'Rohrleitung' AND dn = ? AND da = ? AND size = ?
                    ''', (dn, da, size))
                else:
                    cursor.execute('''
                        SELECT value FROM price_list
                        WHERE bauteil = 'Rohrleitung' AND size = ? AND (dn IS NULL OR dn = 0) AND (da IS NULL OR da = 0)
                    ''', (size,))
            else:
                # For regular Bauteil, use the existing logic
                if dn is not None and da is not None:
                    cursor.execute('''
                        SELECT value FROM price_list
                        WHERE bauteil = ? AND dn = ? AND da = ? AND size = ?
                    ''', (bauteil, dn, da, size))
                else:
                    cursor.execute('''
                        SELECT value FROM price_list
                        WHERE bauteil = ? AND size = ? AND (dn IS NULL OR dn = 0) AND (da IS NULL OR da = 0)
                    ''', (bauteil, size))
            
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.rebuild_items_container()
            self.update_gesamtpreis()
            self.page.update()
        else:
            print(f"Invalid index: {index}")

    def rebuild_items_container(self):
        self.items_container.controls.clear()
        for i, item in enumerate(self.items):
            item["remove_button"].on_click = lambda _, idx=i: self.remove_item(idx)
            item_row = ft.Row([
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
            self.items_container.controls.append(item_row)

    def remove_item(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.rebuild_items_container()
            self.update_gesamtpreis()
            self.page.update()
        else:
            print(f"Invalid index: {index}")

    def rechnung_absenden(self, e):
        if self.handle_duplicate_check():
            return
        
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            self.show_snackbar("Bitte füllen Sie alle Felder aus")
            return
        
        client_name = self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value
        client_email = self.client_email_dropdown.value if self.client_email_dropdown.value != "Neue E-Mail" else self.client_email_entry.value
        
        invoice_date = datetime.now().strftime("%Y-%m-%d")
        
        # Filter out items with empty prices
        invoice_items = [
            {
                "description": item["description"].value,
                "dn": item["dn"].value,
                "da": item["da"].value,
                "size": item["size"].value,
                "price": float(item["price"].value) if item["price"].value else 0,
                "quantity": int(item["quantity"].value),
                "taetigkeit": item["taetigkeit"].value
            }
            for item in self.items
            if item["price"].value and float(item["price"].value) > 0
        ]
        
        total = sum(item["price"] * item["quantity"] for item in invoice_items)
        
        invoice_data = {
            "client_name": client_name,
            "client_email": client_email,
            "invoice_date": invoice_date,
            "items": invoice_items,
            "total": total
        }
        
        if self.rechnung_einfuegen(invoice_data):
            pdf_path = self.pdf_generieren(invoice_data)
            self.show_snackbar(f"Rechnung erfolgreich erstellt und gespeichert als: {pdf_path}")
            self.update_client_dropdowns()
            self.reset_form()
        else:
            self.show_snackbar("Fehler beim Erstellen der Rechnung")
        
        self.page.update()

    def rechnung_einfuegen(self, invoice_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoices (client_name, client_email, invoice_date, total)
            VALUES (?, ?, ?, ?)
        ''', (invoice_data["client_name"], invoice_data["client_email"], invoice_data["invoice_date"], invoice_data["total"]))
            invoice_id = cursor.lastrowid
        
            for item in invoice_data["items"]:
             cursor.execute('''
                INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity, taetigkeit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, item["description"], item["dn"], item["da"], item["size"], item["price"], item["quantity"], item["taetigkeit"]))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    

    def reset_form(self):
        self.client_name_dropdown.value = None
        self.client_email_dropdown.value = None
        self.client_name_entry.value = ""
        self.client_email_entry.value = ""
        self.client_name_entry.visible = False
        self.client_email_entry.visible = False
        self.items.clear()
        self.items_container.controls.clear()
        self.add_item()  # Fügt nur eine leere Artikelzeile hinzu
        self.update_gesamtpreis()
        self.page.update()
        
        # ... (rest of the rechnung_absenden implementation)

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
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity, taetigkeit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_data['id'], item['description'], item['dn'], item['da'], item['size'], item['price'], item['quantity'], item['taetigkeit']))

            conn.commit()
            self.show_snackbar("Rechnung erfolgreich aktualisiert")
            return True
        except sqlite3.Error as e:
            print(f"Ein Fehler ist aufgetreten: {e}")
            conn.rollback()
            self.show_snackbar("Fehler beim Aktualisieren der Rechnung")
            return False
        finally:
            conn.close()
        
        # ... (rest of the update_rechnung implementation)

    def rechnungen_abrufen(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.id, i.client_name, i.client_email, i.invoice_date, i.total
            FROM invoices i
            ORDER BY i.invoice_date DESC
        ''')
        rechnungen = cursor.fetchall()
        conn.close()
        return rechnungen

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
            self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
            self.page.snack_bar.open = True
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
        quantity = int(item["quantity"].value) if item["quantity"].value else 0
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
        
        # ... (rest of the update_rechnung implementation)

def main(page: ft.Page):
    app = InvoicingApp()
    app.main(page)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)