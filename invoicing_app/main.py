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
        self.client_name_dropdown = None
        self.client_email_dropdown = None
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", visible=False)
        self.client_email_entry = ft.TextField(label="Neue Kunden-E-Mail", visible=False)
        self.items = []
        self.items_container = None
        self.gesamtpreis_text = None
        self.absenden_btn = None
        self.main_column = None

    def main(self, page: ft.Page):
        self.page = page
        self.page.title = "Rechnungserstellung"
        self.setup_ui()

    def setup_ui(self):
        self.client_name_dropdown = ft.Dropdown(
            label="Kundenname",
            options=[ft.dropdown.Option("Neuer Kunde")] + [ft.dropdown.Option(name) for name in self.get_unique_customer_names()],
            on_change=self.toggle_name_entry
        )
        self.client_email_dropdown = ft.Dropdown(
            label="Kunden-E-Mail",
            options=[ft.dropdown.Option("Neue E-Mail")] + [ft.dropdown.Option(email) for email in self.get_unique_customer_emails()],
            on_change=self.toggle_email_entry
        )
        
        self.items_container = ft.Column()
        self.gesamtpreis_text = ft.Text("Gesamtpreis: €0.00")
        self.absenden_btn = ft.FilledButton(text="Rechnung absenden", on_click=self.rechnung_absenden, adaptive=True)
        
        add_item_btn = ft.ElevatedButton("Artikel hinzufügen", on_click=lambda _: self.add_item())
        
        self.main_column = ft.Column([
            self.client_name_dropdown,
            self.client_name_entry,
            self.client_email_dropdown,
            self.client_email_entry,
            add_item_btn,
            self.items_container,
            self.gesamtpreis_text,
            self.absenden_btn
        ])
        
        self.page.add(self.main_column)
        self.update_customer_dropdowns()

    def add_item(self):
        new_item = self.create_item_fields()
        self.items.append(new_item)
        self.items_container.controls.append(
            ft.Row([
                new_item["description"],
                new_item["dn"],
                new_item["da"],
                new_item["size"],
                new_item["price"],
                new_item["quantity"],
                ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _, item=new_item: self.remove_item(item))
            ])
        )
        self.page.update()

    def create_item_fields(self, item_data=None):
        item = {
            "description": ft.Dropdown(
                label="Bauteil",
                options=[ft.dropdown.Option(b) for b in self.get_unique_bauteil_values()],
                value=item_data["item_description"] if item_data else None
            ),
            "dn": ft.Dropdown(label="DN", options=[], value=item_data["dn"] if item_data else None),
            "da": ft.Dropdown(label="DA", options=[], value=item_data["da"] if item_data else None),
            "size": ft.Dropdown(label="Größe", options=[], value=item_data["size"] if item_data else None),
            "price": ft.TextField(label="Preis", read_only=True, value=item_data["item_price"] if item_data else None),
            "quantity": ft.TextField(label="Menge", value=item_data["quantity"] if item_data else "1")
        }
        
        item["description"].on_change = lambda _: self.update_item_options("description", item)
        item["dn"].on_change = lambda _: self.update_item_options("dn", item)
        item["da"].on_change = lambda _: self.update_item_options("da", item)
        item["size"].on_change = lambda _: self.update_item_options("size", item)
        item["quantity"].on_change = lambda _: self.update_gesamtpreis()
        
        return item

    def update_item_options(self, changed_field, item):
        print(f"Debug: update_item_options aufgerufen mit changed_field: {changed_field}")
        bauteil = item["description"].value
        selected_dn = item["dn"].value
        selected_da = item["da"].value
        selected_size = item["size"].value
        print(f"Debug: Aktuelle Werte vor Aktualisierung - Bauteil: {bauteil}, DN: {selected_dn}, DA: {selected_da}, Größe: {selected_size}")

        if bauteil:
            available_options = self.get_available_options(bauteil)
            
            if changed_field == "description":
                dn_da_pairs = sorted(set((dn, da) for dn, da, _ in available_options if dn != 0.0 and da != 0.0))
                
                if dn_da_pairs:
                    item["dn"].visible = item["da"].visible = True
                    item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn, _ in dn_da_pairs]
                    item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for _, da in dn_da_pairs]
                else:
                    item["dn"].visible = item["da"].visible = False
                    item["dn"].value = item["da"].value = None

                item["size"].options = []
                item["size"].value = None

            elif changed_field in ["dn", "da"]:
                selected_value = item[changed_field].value
                if selected_value:
                    if changed_field == "dn":
                        matching_da = next((da for dn, da, _ in available_options if dn == float(selected_value)), None)
                        item["da"].value = f"{matching_da:.1f}" if matching_da else None
                    else:  # changed_field == "da"
                        matching_dn = next((dn for dn, da, _ in available_options if da == float(selected_value)), None)
                        item["dn"].value = f"{matching_dn:.0f}" if float(matching_dn).is_integer() else f"{matching_dn}"

            size_options = sorted(set(size for dn, da, size in available_options 
                            if (item["dn"].value is None or dn == float(item["dn"].value)) 
                            and (item["da"].value is None or da == float(item["da"].value))))
            
            # Custom sorting function for size ranges
            def sort_key(size):
                if ' - ' in size:
                    return float(size.split(' - ')[0])
                return float(size) if size.replace('.', '').isdigit() else float('inf')
            
            # Sort size options using the custom sorting function
            size_options = sorted(size_options, key=sort_key)
            
            item["size"].options = [ft.dropdown.Option(size) for size in size_options if size != '0']
            
            # Only set the size value if it's a new item or if the size was changed
            if changed_field in ["description", "dn", "da"] and not item["size"].value:
                item["size"].value = size_options[0] if size_options else None

        print(f"Debug: Werte nach Aktualisierung - Bauteil: {bauteil}, DN: {item['dn'].value}, DA: {item['da'].value}, Größe: {item['size'].value}")
        
        self.update_price(item)
        self.page.update()

    def update_price(self, item):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        
        if all([bauteil, size]) and (dn is None or da is None or (dn and da)):
            price = self.get_price(bauteil, float(dn) if dn else 0.0, float(da) if da else 0.0, size)
            item["price"].value = f"{price:.2f}" if price else ""
        else:
            item["price"].value = ""
        
        self.update_gesamtpreis()

    def rechnung_bearbeiten(self, rechnung_id):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT i.client_name, i.client_email, ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity
            FROM invoices i
            JOIN invoice_items ii ON i.id = ii.invoice_id
            WHERE i.id = ?
        ''', (rechnung_id,))
        invoice_data = cursor.fetchall()
        conn.close()

        if not invoice_data:
            print(f"Keine Rechnung mit ID {rechnung_id} gefunden.")
            return

        self.client_name_dropdown.value = invoice_data[0][0]
        self.client_email_dropdown.value = invoice_data[0][1]
        
        self.items.clear()
        self.items_container.controls.clear()
        
        for item_data in invoice_data:
            new_item = self.create_item_fields({
                "item_description": item_data[2],
                "dn": item_data[3],
                "da": item_data[4],
                "size": item_data[5],
                "item_price": item_data[6],
                "quantity": item_data[7]
            })
            self.items.append(new_item)
            self.items_container.controls.append(
                ft.Row([
                    new_item["description"],
                    new_item["dn"],
                    new_item["da"],
                    new_item["size"],
                    new_item["price"],
                    new_item["quantity"],
                    ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _, item=new_item: self.remove_item(item))
                ])
            )
        
        self.absenden_btn.text = "Rechnung aktualisieren"
        self.absenden_btn.on_click = lambda _: self.update_rechnung(rechnung_id)
        
        self.update_gesamtpreis()
        self.page.update()

    def update_rechnung(self, rechnung_id):
        # Implement the logic to update an existing invoice in the database
        # This is a placeholder implementation
        print(f"Updating invoice {rechnung_id}")
        # Update invoice data in the database
        # Regenerate PDF
        self.pdf_neu_generieren(rechnung_id)
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Rechnung erfolgreich aktualisiert")))

    def pdf_neu_generieren(self, rechnung_id):
        # Implement the logic to regenerate the PDF for an existing invoice
        # This is a placeholder implementation
        print(f"Regenerating PDF for invoice {rechnung_id}")
        # Fetch invoice data from the database
        # Generate new PDF using reportlab
        # Save the PDF
        self.page.show_snack_bar(ft.SnackBar(content=ft.Text("PDF erfolgreich neu generiert")))

    def rechnung_loeschen_bestaetigen(self, rechnung_id):
        def delete_invoice(e):
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (rechnung_id,))
            cursor.execute("DELETE FROM invoices WHERE id = ?", (rechnung_id,))
            conn.commit()
            conn.close()
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("Rechnung erfolgreich gelöscht")))
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Rechnung löschen"),
            content=ft.Text("Sind Sie sicher, dass Sie diese Rechnung löschen möchten?"),
            actions=[
                ft.TextButton("Abbrechen", on_click=lambda _: setattr(dialog, 'open', False)),
                ft.TextButton("Löschen", on_click=delete_invoice),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def update_customer_dropdowns(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT client_name, client_email FROM invoices")
        customers = cursor.fetchall()
        conn.close()

        unique_names = set()
        unique_emails = set()

        for name, email in customers:
            if name:
                unique_names.add(name)
            if email:
                unique_emails.add(email)

        self.client_name_dropdown.options = [ft.dropdown.Option("Neuer Kunde")] + [
            ft.dropdown.Option(name) for name in sorted(unique_names)
        ]
        self.client_email_dropdown.options = [ft.dropdown.Option("Neue E-Mail")] + [
            ft.dropdown.Option(email) for email in sorted(unique_emails)
        ]

        self.client_name_dropdown.update()
        self.client_email_dropdown.update()

    def get_unique_bauteil_values(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT bauteil FROM price_list ORDER BY bauteil")
        bauteile = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out empty values
        conn.close()
        return bauteile

    def remove_item(self, item):
        self.items.remove(item)
        self.items_container.controls = [
            control for control in self.items_container.controls
            if control.controls[0] != item["description"]
        ]
        self.update_gesamtpreis()
        self.page.update()

    def update_gesamtpreis(self):
        total = sum(
            float(item["price"].value) * float(item["quantity"].value)
            for item in self.items
            if item["price"].value and item["quantity"].value
        )
        self.gesamtpreis_text.value = f"Gesamtpreis: €{total:.2f}"
        self.page.update()

    def get_available_options(self, bauteil):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT dn, da, size FROM price_list WHERE bauteil = ?", (bauteil,))
        options = cursor.fetchall()
        conn.close()
        return options

    def get_price(self, bauteil, dn, da, size):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        query = "SELECT value FROM price_list WHERE bauteil = ? AND size = ?"
        params = [bauteil, size]
        
        if dn != 0.0:
            query += " AND dn = ?"
            params.append(dn)
        if da != 0.0:
            query += " AND da = ?"
            params.append(da)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def neue_rechnung_erstellen(self, e):
        self.client_name_dropdown.value = None
        self.client_email_dropdown.value = None
        self.client_name_entry.value = ""
        self.client_email_entry.value = ""
        self.items.clear()
        self.items_container.controls.clear()
        self.add_item()
        self.absenden_btn.text = "Rechnung absenden"
        self.absenden_btn.on_click = self.rechnung_absenden
        self.gesamtpreis_text.value = "Gesamtpreis: €0.00"
        
        if self.main_column.controls and isinstance(self.main_column.controls[0], ft.ElevatedButton):
            self.main_column.controls.pop(0)
        
        self.page.update()

    def get_db_connection(self):
        return sqlite3.connect(get_db_path())

    def toggle_name_entry(self, e):
        if self.client_name_dropdown.value == "Neuer Kunde":
            self.client_name_entry.visible = True
        else:
            self.client_name_entry.visible = False
        self.page.update()

    def toggle_email_entry(self, e):
        if self.client_email_dropdown.value == "Neue E-Mail":
            self.client_email_entry.visible = True
        else:
            self.client_email_entry.visible = False
        self.page.update()


    def get_unique_customer_names(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT client_name FROM invoices ORDER BY client_name')
        names = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out empty names
        conn.close()
        return names

    def get_unique_customer_emails(self):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT client_email FROM invoices ORDER BY client_email')
        emails = [row[0] for row in cursor.fetchall() if row[0]]  # Filter out empty emails
        conn.close()
        return emails
    
    def rechnung_absenden(self, e):
        if not self.client_name_dropdown.value or not self.client_email_dropdown.value or not self.items:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        try:
            total = self.calculate_total()
            rechnungsdaten = {
                'client_name': self.client_name_dropdown.value if self.client_name_dropdown.value != "Neuer Kunde" else self.client_name_entry.value,
                'client_email': self.client_email_dropdown.value if self.client_email_dropdown.value != "Neue E-Mail" else self.client_email_entry.value,
                'invoice_date': datetime.now().strftime('%Y-%m-%d'),
                'total': total,
                'items': [
                    {
                        'description': item["description"].value,
                        'dn': item["dn"].value,
                        'da': item["da"].value,
                        'size': item["size"].value,
                        'price': float(item["price"].value),
                        'quantity': int(item["quantity"].value)
                    }
                    for item in self.items
                    if item["description"].value and item["price"].value and item["quantity"].value
                ]
            }
            
            if not rechnungsdaten['items']:
                self.page.snack_bar = ft.SnackBar(content=ft.Text("Bitte fügen Sie mindestens einen gültigen Artikel hinzu"))
                self.page.overlay.append(self.page.snack_bar)
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            self.rechnung_einfuegen(**rechnungsdaten)
            
            # Aktualisiere die Dropdown-Menüs
            self.update_customer_dropdowns()
            
            # Clear fields
            self.client_name_dropdown.value = None
            self.client_email_dropdown.value = None
            self.client_name_entry.value = ""
            self.client_email_entry.value = ""
            self.items.clear()
            self.items_container.controls.clear()
            self.add_item()
            
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung erfolgreich erstellt!"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.page.update()
        except ValueError:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Ungültiger Preis oder Menge"))
            self.page.overlay.append(self.page.snack_bar)
            self.page.snack_bar.open = True
            self.page.update()

    def calculate_total(self):
        return sum(
            float(item["price"].value) * int(item["quantity"].value)
            for item in self.items
            if item["price"].value and item["quantity"].value
        )

    def rechnung_einfuegen(self, client_name, client_email, invoice_date, total, items):
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoices (client_name, client_email, invoice_date, total)
                VALUES (?, ?, ?, ?)
            ''', (client_name, client_email, invoice_date, total))
            invoice_id = cursor.lastrowid
            
            for item in items:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (invoice_id, item['description'], item['dn'], item['da'], item['size'], item['price'], item['quantity']))
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            conn.rollback()
        finally:
            conn.close()


def main(page: ft.Page):
    app = InvoicingApp()
    app.main(page)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)