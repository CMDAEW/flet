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

    def update_gesamtpreis(self):
        total = sum(
            float(item["subtotal"].value.replace('€', '')) 
            for item in self.items 
            if item["subtotal"].value
        )
        self.gesamtpreis_text.value = f"Gesamtpreis: €{total:.2f}"
        self.page.update()

    def add_item(self):
        bauteil_values = self.get_unique_bauteil_values()
        
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
                width=100,
                read_only=True,
                filled=True,
                bgcolor=ft.colors.GREY_200
            )
        }

        # Set up event handlers for the dropdowns
        new_item["description"].on_change = lambda _: self.update_item_options(new_item, "description")
        new_item["dn"].on_change = lambda _: self.update_item_options(new_item, "dn")
        new_item["da"].on_change = lambda _: self.update_item_options(new_item, "da")
        new_item["size"].on_change = lambda _: self.update_item_options(new_item, "size")
        new_item["quantity"].on_change = lambda _: self.update_item_subtotal(new_item)

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
        self.update_item_subtotal(new_item)
        self.update_gesamtpreis()
        self.page.update()

    def get_unique_client_names(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT client_name FROM invoices ORDER BY client_name')
            client_names = [row[0] for row in cursor.fetchall()]
            return client_names
        except sqlite3.Error as e:
            print(f"Fehler beim Abrufen der Kundennamen: {e}")
            return []
        finally:
            conn.close()

    def get_unique_customer_emails(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT client_email FROM invoices ORDER BY client_email')
        emails = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out empty emails
        conn.close()
        return emails
    
    def update_item_subtotal(self, item):
        price = float(item["price"].value) if item["price"].value else 0
        quantity = int(item["quantity"].value) if item["quantity"].value else 0
        subtotal = price * quantity
        item["subtotal"].value = f"€{subtotal:.2f}"
        self.update_gesamtpreis()
        self.page.update()
    
    def rechnung_absenden(self, e):
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
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
            "client_name": client_name,
            "client_email": client_email,
            "invoice_date": invoice_date,
            "total": total,
            "items": invoice_items
        }
        
        if self.rechnung_einfuegen(invoice_data):
            pdf_path = self.pdf_generieren(invoice_data)
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Rechnung erfolgreich erstellt und gespeichert als: {pdf_path}"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.reset_form()
        else:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Fehler beim Erstellen der Rechnung"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
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


    def route_change(self, route):
        self.page.views.clear()
        if route.route == "/":
            self.page.views.append(
                ft.View(
                    "/",
                    [
                        # Your main page controls here
                    ]
                )
            )
        # Add other routes as needed
        self.page.update()

    def build_ui(self):
        customer_names = self.get_unique_client_names()
        customer_emails = self.get_unique_customer_emails()

        self.client_name_dropdown = ft.Dropdown(
            label="Kundenname",
            options=[ft.dropdown.Option(name) for name in customer_names] + [ft.dropdown.Option("Neuer Kunde")],
            width=300,
            on_change=self.toggle_name_entry
        )
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", visible=False, width=300)

        self.client_email_dropdown = ft.Dropdown(
            label="Kunden-E-Mail",
            options=[ft.dropdown.Option(email) for email in customer_emails] + [ft.dropdown.Option("Neue E-Mail")],
            width=300,
            on_change=self.toggle_email_entry
        )
        self.client_email_entry = ft.TextField(label="Neue Kunden-E-Mail", visible=False, width=300)

        add_item_button = ft.ElevatedButton("Artikel hinzufügen", on_click=self.add_item)
        show_invoices_button = ft.ElevatedButton("Rechnungen anzeigen", on_click=self.rechnungen_anzeigen)

        main_view = ft.Column([
            ft.Text("Rechnungs-App", size=30, weight=ft.FontWeight.BOLD),
            self.client_name_dropdown,
            self.client_name_entry,
            self.client_email_dropdown,
            self.client_email_entry,
            add_item_button,
            self.items_container,
            self.gesamtpreis_text,
            self.submit_invoice_button,
            self.update_invoice_button,
            show_invoices_button
        ])

        return main_view

    # ... (rest of the class methods)

    def main(self, page: ft.Page):
        self.page = page
        self.page.title = "Rechnungs-App"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.fonts = {
            "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
        }
        self.page.theme = ft.Theme(font_family="Roboto")
        self.page.adaptive = True

        self.submit_invoice_button = ft.ElevatedButton("Rechnung absenden", on_click=self.rechnung_absenden)
        self.update_invoice_button = ft.ElevatedButton("Rechnung aktualisieren", visible=False)

        # Build the UI and add it to the page
        main_view = self.build_ui()
        self.page.add(main_view)

        self.page.on_route_change = self.route_change
        self.page.go('/')

def main(page: ft.Page):
    app = InvoicingApp()
    app.main(page)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)

    def get_unique_bauteil_values(self):
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

        # Update the main form with the invoice data
        self.client_name_dropdown.value = invoice_items[0][1]
        self.client_email_dropdown.value = invoice_items[0][2]
        
        # Clear existing items
        self.items.clear()
        self.items_container.controls.clear()

        for item in invoice_items:
            bauteil = item[5]
            new_item = self.create_item_dict(bauteil, item[6], item[7], item[8], item[9], item[10])
            self.items.append(new_item)
            item_row = self.create_item_row(new_item)
            self.items_container.controls.append(item_row)

        # Update the total price
        self.update_gesamtpreis()

        # Change the "Rechnung aktualisieren" button to be visible and update its on_click event
        self.update_invoice_button.visible = True
        self.update_invoice_button.on_click = lambda _: self.update_rechnung(rechnung_id)

        # Hide the "Rechnung absenden" button
        self.submit_invoice_button.visible = False

        # Update the page
        self.page.update()

        # Close the invoice list dialog
        self.close_dialog(self.page.dialog)

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


    def update_item_subtotal(self, item):
        price = float(item["price"].value) if item["price"].value else 0
        quantity = int(item["quantity"].value) if item["quantity"].value else 0
        subtotal = price * quantity
        item["subtotal"].value = f"€{subtotal:.2f}"
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
        self.update_item_subtotal(item)

    def update_gesamtpreis(self):
        total = sum(
            float(item["subtotal"].value.replace('€', '')) 
            for item in self.items 
            if item["subtotal"].value
        )
        self.gesamtpreis_text.value = f"Gesamtpreis: €{total:.2f}"
        self.page.update()

    def update_item_options(self, item, changed_field):
        bauteil = item["description"].value

        if bauteil:
            if changed_field == "description":
                self.reset_item_fields(item)
                self.update_item_dropdowns(item, bauteil)
            elif changed_field in ["dn", "da", "size"]:
                self.update_compatible_options(item, bauteil)

        self.update_price(item)
        self.update_item_row_layout(item)
        self.page.update()

    def update_item_dropdowns(self, item, bauteil):
        dn_options = self.get_available_dn(bauteil)
        da_options = self.get_available_da(bauteil)
        size_options = self.get_available_sizes(bauteil)

        item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
        item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
        item["size"].options = [ft.dropdown.Option(value) for value in size_options]

        item["dn"].visible = bool(dn_options)
        item["da"].visible = bool(da_options)

    def update_compatible_options(self, item, bauteil):
        selected_dn = float(item["dn"].value) if item["dn"].value else None
        selected_da = float(item["da"].value) if item["da"].value else None
        selected_size = item["size"].value

        available_options = self.get_available_options(bauteil)

        # ... (rest of the method remains the same)

    def reset_item_fields(self, item):
        item["dn"].value = None
        item["da"].value = None
        item["size"].value = None

    def update_item_dropdowns(self, item, available_options):
        dn_options = sorted(set(dn for dn, _, _ in available_options if dn != 0))
        da_options = sorted(set(da for _, da, _ in available_options if da != 0))
        size_options = sorted(set(size for _, _, size in available_options), 
                              key=lambda x: float(x.split('-')[0].strip().rstrip('mm')))

        item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
        item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
        item["size"].options = [ft.dropdown.Option(value) for value in size_options]

        item["dn"].visible = bool(dn_options)
        item["da"].visible = bool(da_options)

    def update_item_row_layout(self, item):
        item_row = next((row for row in self.items_container.controls if item["description"] in row.controls), None)
        if item_row is None:
            print(f"Could not find item row for {item['description'].value}")
            return

        new_controls = [
            item["description"],
            item["dn"] if item["dn"].visible else ft.Container(width=0),
            item["da"] if item["da"].visible else ft.Container(width=0),
            item["size"],
            item["price"],
            item["quantity"],
            item["subtotal"],
            item_row.controls[-1]  # Keep the delete button
        ]

        if any(control is None for control in new_controls):
            print(f"Found None control in new_controls for {item['description'].value}")
            return

        item_row.controls = new_controls
        self.page.update()

    def update_compatible_options(self, item, available_options):
        selected_dn = float(item["dn"].value) if item["dn"].value else None
        selected_da = float(item["da"].value) if item["da"].value else None
        selected_size = item["size"].value

        if selected_dn:
            compatible_da = [da for dn, da, _ in available_options if dn == selected_dn]
            if compatible_da and not item["da"].value:
                item["da"].value = f"{compatible_da[0]:.1f}"

        if selected_da:
            compatible_dn = [dn for dn, da, _ in available_options if da == selected_da]
            if compatible_dn and not item["dn"].value:
                item["dn"].value = f"{compatible_dn[0]:.0f}" if float(compatible_dn[0]).is_integer() else f"{compatible_dn[0]}"

        if selected_size:
            matching_dn_da = [(dn, da) for dn, da, size in available_options if size == selected_size]
            if matching_dn_da:
                dn, da = matching_dn_da[0]
                if not item["dn"].value:
                    item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                if not item["da"].value:
                    item["da"].value = f"{da:.1f}"

        # Update size options based on current DN and DA selection
        matching_sizes = [
            size for dn, da, size in available_options 
            if (selected_dn is None or dn == selected_dn) and (selected_da is None or da == selected_da)
        ]
        size_options = sorted(set(matching_sizes), key=lambda x: float(x.split('-')[0].strip().rstrip('mm')))
        item["size"].options = [ft.dropdown.Option(value) for value in size_options]

    def get_available_options(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT dn, da, size FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0', (bauteil,))
        options = cursor.fetchall()
        conn.close()
        return options

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

    def get_price(self, bauteil, dn, da, size):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT value FROM price_list
                WHERE bauteil = ? AND dn = ? AND da = ? AND size = ?
            ''', (bauteil, dn, da, size))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()

    def remove_item(self, item):
        self.items.remove(item)
        self.items_container.controls = [
            control for control in self.items_container.controls
            if control.controls[0] != item["description"]
        ]
        self.update_gesamtpreis()
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
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, item["description"], item["dn"], item["da"], item["size"], item["price"], item["quantity"]))
            
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
        self.items.clear()
        self.items_container.controls.clear()
        self.update_gesamtpreis()
        self.add_item()  # Add an initial empty item
        self.update_invoice_button.visible = False
        self.submit_invoice_button.visible = True
        self.page.update()
        
        # ... (rest of the rechnung_absenden implementation)

    def update_rechnung(self, rechnung_id):
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        client_name = self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value
        client_email = self.client_email_dropdown.value if self.client_email_dropdown.value != "Neue E-Mail" else self.client_email_entry.value
        
        invoice_date = datetime.now().strftime("%Y-%m-%d")
        total = sum(float(item["price"].value) * int(item["quantity"].value) for item in self.items)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE invoices 
                SET client_name=?, client_email=?, invoice_date=?, total=?
                WHERE id=?
            ''', (client_name, client_email, invoice_date, total, rechnung_id))
            
            cursor.execute('DELETE FROM invoice_items WHERE invoice_id=?', (rechnung_id,))
            
            for item in self.items:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (rechnung_id, item["description"].value, item["dn"].value, item["da"].value, item["size"].value, float(item["price"].value), int(item["quantity"].value)))
            
            conn.commit()
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung erfolgreich aktualisiert"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.reset_form()
            self.rechnungen_anzeigen(None)  # Refresh the invoice list
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            conn.rollback()
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Fehler beim Aktualisieren der Rechnung"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
        finally:
            conn.close()
            self.page.update()
        
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

    def pdf_generieren(self, rechnungsdaten):
        # Get the directory where the script is running from
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Generate a unique filename
        pdf_dateiname = f"Rechnung_{rechnungsdaten['client_name']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_path = os.path.join(script_dir, pdf_dateiname)

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
        data = [['Beschreibung', 'DN', 'DA', 'Größe', 'Preis', 'Menge', 'Gesamt']]
        for item in rechnungsdaten['items']:
            row = [
                item['description'],
                item['dn'],
                item['da'],
                item['size'],
                f"€{item['price']:.2f}",
                str(item['quantity']),
                f"€{item['price'] * item['quantity']:.2f}"
            ]
            data.append(row)

        # Add total row
        data.append(['', '', '', '', '', 'Gesamtbetrag:', f"€{rechnungsdaten['total']:.2f}"])

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
            ('ALIGN', (0, -1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)

        # Build the PDF
        doc.build(elements)

        return pdf_path

    def rechnung_loeschen(self, rechnung_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (rechnung_id,))
            cursor.execute('DELETE FROM invoices WHERE id = ?', (rechnung_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def create_item_dict(self, bauteil, dn, da, size, price, quantity):
        return {
            "description": ft.Dropdown(
                label="Artikelbeschreibung",
                width=300,
                options=[ft.dropdown.Option(b) for b in get_unique_bauteil_values()],
                value=bauteil
            ),
            "dn": ft.Dropdown(
                label="DN",
                width=80,
                options=[ft.dropdown.Option(f"{d:.0f}" if float(d).is_integer() else f"{d}") for d in self.get_available_dn(bauteil)],
                value=str(dn) if dn and dn != 0 else None,
                visible=bool(dn and dn != 0)
            ),
            "da": ft.Dropdown(
                label="DA",
                width=80,
                options=[ft.dropdown.Option(f"{d:.1f}") for d in self.get_available_da(bauteil)],
                value=str(da) if da and da != 0 else None,
                visible=bool(da and da != 0)
            ),
            "size": ft.Dropdown(
                label="Dämmdicke",
                width=120,
                options=[ft.dropdown.Option(s) for s in self.get_available_sizes(bauteil)],
                value=size
            ),
            "price": ft.TextField(
                label="Preis",
                width=100,
                value=str(price),
                read_only=True,
                filled=True,
                bgcolor=ft.colors.GREY_200
            ),
            "quantity": ft.TextField(
                label="Menge",
                width=80,
                value=str(quantity)
            ),
            "subtotal": ft.TextField(
                label="Zwischensumme",
                width=120,
                value=f"€{float(price) * int(quantity):.2f}",
                read_only=True,
                filled=True,
                bgcolor=ft.colors.GREY_200
            )
        }

    def create_item_row(self, item):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    item["description"],
                    item["dn"] if item["dn"].visible else ft.Container(width=0),
                    item["da"] if item["da"].visible else ft.Container(width=0),
                    item["size"],
                ], wrap=True),
                ft.Row([
                    item["price"],
                    item["quantity"],
                    item["subtotal"],
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        on_click=lambda _, item=item: self.remove_item(item)
                    )
                ], wrap=True)
            ]),
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=5,
            padding=5,
            margin=ft.margin.only(bottom=10)
        )

    def setup_item_event_handlers(self, item):
        item["description"].on_change = lambda _, item=item: self.update_item_options(item, "description")
        item["dn"].on_change = lambda _, item=item: self.update_item_options(item, "dn")
        item["da"].on_change = lambda _, item=item: self.update_item_options(item, "da")
        item["size"].on_change = lambda _, item=item: self.update_item_options(item, "size")
        item["quantity"].on_change = lambda _, item=item: self.update_item_subtotal(item)

    def get_available_dn(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT dn FROM price_list WHERE bauteil = ? AND dn != 0 ORDER BY dn', (bauteil,))
        dn_values = [row[0] for row in cursor.fetchall()]
        conn.close()
        return dn_values

    def get_available_da(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND da != 0 ORDER BY da', (bauteil,))
        da_values = [row[0] for row in cursor.fetchall()]
        conn.close()
        return da_values

    def get_available_sizes(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT size FROM price_list WHERE bauteil = ? ORDER BY size', (bauteil,))
        size_values = [row[0] for row in cursor.fetchall()]
        conn.close()
        return size_values

def main(page: ft.Page):
    app = InvoicingApp()
    app.main(page)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)