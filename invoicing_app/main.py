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
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

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
                FOREIGN KEY (invoice_id) REFERENCES invoices (id)
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
        
        conn.commit()
        logging.info("Datenbankinitialisierung erfolgreich abgeschlossen.")
    except Exception as e:
        logging.error(f"Fehler bei der Datenbankinitialisierung: {e}")
        conn.rollback()
    finally:
        conn.close()

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

    def build_ui(self):
        bauteil_values = get_unique_bauteil_values()
        customer_names = self.get_unique_client_names()
        customer_emails = self.get_unique_customer_emails()

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

        absenden_btn = ft.FilledButton(text="Abrechnung absenden", on_click=self.rechnung_absenden, adaptive=True)
        ohne_preise_btn = ft.OutlinedButton(text="Rechnung ohne Preise generieren", on_click=self.rechnung_ohne_preise_generieren, adaptive=True)
        rechnungen_anzeigen_btn = ft.OutlinedButton(text="Vorhandene Rechnungen anzeigen", on_click=self.rechnungen_anzeigen, adaptive=True)
        add_item_button = ft.ElevatedButton("Artikel hinzufügen", on_click=lambda _: self.add_item(), adaptive=True)
        
        main_column = ft.Column([
            self.client_name_dropdown,
            self.client_name_entry,
            self.client_email_dropdown,
            self.client_email_entry,
            add_item_button,
            self.items_container,
            self.gesamtpreis_text,
            ft.Row([absenden_btn, ohne_preise_btn, rechnungen_anzeigen_btn])
        ], scroll=ft.ScrollMode.ALWAYS)

        scrollable_view = ft.Row(
            [main_column],
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
        )

        # Add an initial empty item
        self.add_item()

        return scrollable_view

    def rechnung_ohne_preise_generieren(self, e):
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            self.show_snackbar("Bitte füllen Sie alle Felder aus")
            return
        
        client_name = self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value
        client_email = self.client_email_dropdown.value if self.client_email_dropdown.value != "Neue E-Mail" else self.client_email_entry.value
        
        invoice_date = datetime.now().strftime("%Y-%m-%d")
        
        invoice_items = [
            {
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
        doc = SimpleDocTemplate(pdf_path, pagesize=letter)
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
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.fonts = {
            "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
        }
        self.page.theme = ft.Theme(font_family="Roboto")
        self.page.adaptive = True

        self.submit_invoice_button = ft.ElevatedButton("Abrechnung absenden", on_click=self.rechnung_absenden)
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
        
        self.page.dialog = rechnungs_dialog
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.id, i.client_name, i.client_email, i.invoice_date, i.total,
                   ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity
            FROM invoices i
            JOIN invoice_items ii ON i.id = ii.invoice_id
            WHERE i.id = ?
        ''', (rechnung_id,))
        invoice_items = cursor.fetchall()
        conn.close()

        if not invoice_items:
            print(f"No invoice found with id {rechnung_id}")
            return

        # Clear existing items
        self.items.clear()
        self.items_container.controls.clear()

        # Set client name and email
        self.client_name_dropdown.value = invoice_items[0][1]
        self.client_email_dropdown.value = invoice_items[0][2]

        # Add items from the invoice
        for item in invoice_items:
            self.add_item()
            new_item = self.items[-1]
            new_item["description"].value = item[5]
            new_item["dn"].value = str(item[6]) if item[6] is not None else None
            new_item["da"].value = str(item[7]) if item[7] is not None else None
            new_item["size"].value = item[8]
            new_item["price"].value = str(item[9])
            new_item["quantity"].value = str(item[10])

            # Update options for the item
            self.update_item_options(new_item, "description")

        # Update total price
        self.update_gesamtpreis()

        # Change the "Rechnung absenden" button to "Rechnung aktualisieren"
        update_button = next((control for control in self.page.controls if isinstance(control, ft.FilledButton) and control.text == "Rechnung absenden"), None)
        if update_button:
            update_button.text = "Rechnung aktualisieren"
            update_button.on_click = lambda _: self.rechnung_aktualisieren(rechnung_id)

        self.page.update()

    def rechnung_bearbeiten(self, rechnung_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.id, i.client_name, i.client_email, i.invoice_date, i.total,
                   ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity
            FROM invoices i
            JOIN invoice_items ii ON i.id = ii.invoice_id
            WHERE i.id = ?
        ''', (rechnung_id,))
        invoice_items = cursor.fetchall()
        conn.close()

        if not invoice_items:
            print(f"No invoice found with id {rechnung_id}")
            return

        # Clear existing items
        self.items.clear()
        self.items_container.controls.clear()

        # Set client name and email
        self.client_name_dropdown.value = invoice_items[0][1]
        self.client_email_dropdown.value = invoice_items[0][2]

        # Add items from the invoice
        for item in invoice_items:
            self.add_item()
            new_item = self.items[-1]
            new_item["description"].value = item[5]
            new_item["dn"].value = str(item[6]) if item[6] is not None else None
            new_item["da"].value = str(item[7]) if item[7] is not None else None
            new_item["size"].value = item[8]
            new_item["price"].value = str(item[9])
            new_item["quantity"].value = str(item[10])

            # Update options for the item
            self.update_item_options(new_item, "description")
            
            # Update subtotal
            self.update_item_subtotal(new_item)

        # Update total price
        self.update_gesamtpreis()

        # Change the "Rechnung absenden" button to "Rechnung aktualisieren"
        update_button = next((control for control in self.page.controls if isinstance(control, ft.FilledButton) and control.text == "Rechnung absenden"), None)
        if update_button:
            update_button.text = "Rechnung aktualisieren"
            update_button.on_click = lambda _: self.rechnung_aktualisieren(rechnung_id)

        self.page.update()

    def rechnung_aktualisieren(self, rechnung_id):
        # Similar to rechnung_absenden, but update existing invoice
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()
            return
        
        client_name = self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value
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
            "client_name": client_name,
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

        # ... (rest of the implementation)

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
                        'quantity': item[7]
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
                self.page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung erfolgreich gelöscht"))
                self.page.overlay.append(self.page.snack_bar)
                self.page.snack_bar.open = True
                self.page.dialog.open = False
                self.rechnungen_anzeigen(None)  # Refresh the invoice list
            else:
                self.page.snack_bar = ft.SnackBar(content=ft.Text("Fehler beim Löschen der Rechnung"))
                self.page.overlay.append(self.page.snack_bar)
                self.page.snack_bar.open = True
            self.page.update()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Rechnung löschen"),
            content=ft.Text("Sind Sie sicher, dass Sie diese Rechnung löschen möchten?"),
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
        total = sum(
            float(item["price"].value) * int(item["quantity"].value)
            for item in self.items
            if item["price"].value and item["quantity"].value
        )
        self.gesamtpreis_text.value = f"Gesamtpreis: €{total:.2f}"
        self.page.update()

    def add_item(self):
        bauteil_values = get_unique_bauteil_values()
        
        new_item = {
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                width=200,
                options=[ft.dropdown.Option(b) for b in bauteil_values]
            ),
            "dn": ft.Dropdown(
                label="DN",
                width=100,
                visible=False
            ),
            "da": ft.Dropdown(
                label="DA",
                width=100,
                visible=False
            ),
            "size": ft.Dropdown(
                label="Dämmdicke",
                width=150
            ),
            "price": ft.TextField(
                label="Preis",
                width=100,
                read_only=True,
                filled=True,
                bgcolor=ft.colors.GREY_200
            ),
            "quantity": ft.TextField(label="Menge", width=100, value="1"),
            "subtotal": ft.TextField(
                label="Zwischensumme",
                width=150,
                read_only=True,
                filled=True,
                bgcolor=ft.colors.GREY_200
            )
        }

        # Set up event handlers for the dropdowns and quantity
        new_item["description"].on_change = lambda e: self.update_item_options(new_item, "description")
        new_item["dn"].on_change = lambda e: self.update_item_options(new_item, "dn")
        new_item["da"].on_change = lambda e: self.update_item_options(new_item, "da")
        new_item["size"].on_change = lambda e: self.update_item_options(new_item, "size")
        new_item["quantity"].on_change = lambda e: self.update_item_subtotal(new_item)

        # Check if an identical item already exists
        existing_item = self.find_existing_item(new_item)
        if existing_item:
            # Increase the quantity of the existing item
            current_quantity = int(existing_item["quantity"].value)
            existing_item["quantity"].value = str(current_quantity + 1)
            self.update_item_subtotal(existing_item)
        else:
            # Create a row for the new item
            item_row = ft.Row([
                new_item["description"],
                new_item["dn"],
                new_item["da"],
                new_item["size"],
                new_item["price"],
                new_item["quantity"],
                new_item["subtotal"],
                ft.IconButton(
                    icon=ft.icons.DELETE,
                    on_click=lambda _: self.remove_item(new_item)
                )
            ])

            # Add the new item to the list and update the UI
            self.items.append(new_item)
            self.items_container.controls.append(item_row)

        self.update_gesamtpreis()
        self.page.update()

    def update_item_subtotal(self, item):
        price = float(item["price"].value) if item["price"].value else 0
        quantity = int(item["quantity"].value) if item["quantity"].value else 0
        subtotal = price * quantity
        item["subtotal"].value = f"{subtotal:.2f}"
        self.update_gesamtpreis()
        self.page.update()

    def update_price(self, item):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        
        if bauteil and size:
            dn_value = float(dn) if dn else 0
            da_value = float(da) if da else 0
            price = self.get_price(bauteil, dn_value, da_value, size)
            if price is not None:
                item["price"].value = f"{price:.2f}"
            else:
                item["price"].value = ""
        else:
            item["price"].value = ""
        item["price"].update()
        self.update_item_subtotal(item)  # Update subtotal when price changes
        self.page.update()

    def update_item_options(self, item, changed_field):
        print(f"Updating options for {changed_field}")
        bauteil = item["description"].value
        selected_dn = item["dn"].value
        selected_da = item["da"].value
        selected_size = item["size"].value

        if bauteil:
            available_options = self.get_available_options(bauteil)
            print(f"Available options: {available_options}")

            # Update DN and DA options with available values
            dn_options = sorted(set(dn for dn, _, _ in available_options if dn != 0 and dn is not None))
            da_options = sorted(set(da for _, da, _ in available_options if da != 0 and da is not None))
            
            # Always show DN and DA fields when they are not null
            item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_            item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
            item["dn"].visible = bool(dn_options)
            item["da"].visible = bool(da_options)

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

            # ... (rest of the method remains the same)

        # Update the dropdowns
        item["dn"].update()
        item["da"].update()
        item["size"].update()
        
        # Update the price
        self.update_price(item)

        print(f"Final values - DN: {item['dn'].value}, DA: {item['da'].value}, Size: {item['size'].value}")

        # Ensure the page is updated
        self.page.update()

    def find_existing_item(self, new_item):
        for item in self.items:
            if (item["description"].value == new_item["description"].value and
                item["dn"].value == new_item["dn"].value and
                item["da"].value == new_item["da"].value and
                item["size"].value == new_item["size"].value and
                item["price"].value == new_item["price"].value):
                return item
        return None

def get_unique_bauteil_values():
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT bauteil FROM price_list ORDER BY bauteil')
        bauteil_values = [row[0] for row in cursor.fetchall()]
        conn.close()
        return bauteil_values
    except sqlite3.Error as e:
        print(f"Fehler beim Abrufen der Bauteil-Werte: {e}")
        return []
        
        # ... (rest of the update_rechnung implementation)

def main(page: ft.Page):
    app = InvoicingApp()
    app.main(page)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)