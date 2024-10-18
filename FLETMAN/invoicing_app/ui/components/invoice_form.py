import logging
import sqlite3
import flet as ft
import re
import os
from datetime import datetime

from database.db_operations import get_db_connection
from .invoice_pdf_generator import generate_pdf
from .invoice_form_helpers import (
    load_items, get_dammdicke_options, get_base_price,
    get_material_price, get_taetigkeit_faktor, update_price
)

class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.next_aufmass_nr = self.get_current_aufmass_nr()
        self.cache = {}
        self.article_summaries = []
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        self.current_category = "Aufmaß"
        self.edit_mode = False
        self.edit_row_index = None
        self.article_count = 0
        self.pdf_generated = False  # Neues Attribut zur Verfolgung der PDF-Erstellung

        logging.info("Initializing InvoiceForm")
        self.create_ui_elements()
        self.load_invoice_options()
        self.load_last_invoice_data()  # Neue Methode zum Laden der letzten Rechnungsdaten
        logging.info("Loading data")
        self.load_data()
        load_items(self, self.current_category)
        self.update_price()
        logging.info("InvoiceForm initialization complete")

    def build(self):
        # Build the UI layout
        invoice_details = self.build_invoice_details()
        article_input = self.build_article_input()
        article_list = self.build_article_list()
        summary_and_actions = self.build_summary_and_actions()
        bemerkung_container = self.build_bemerkung_container()

        return ft.Container(
            content=ft.Column(
                [
                    invoice_details,
                    article_input,
                    article_list,
                    bemerkung_container,
                    summary_and_actions,
                ],
                expand=True,
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=20,
            expand=True,
        )

    def create_ui_elements(self):
        # Create UI elements
        self.create_invoice_detail_fields()
        self.create_article_input_fields()
        self.create_action_buttons()
        self.create_article_list_table()
        self.create_summary_fields()

    def create_invoice_detail_fields(self):
        # Invoice detail fields
        self.invoice_detail_fields = {
            'client_name': ft.Dropdown(label="Kunde", on_change=lambda e: self.toggle_new_entry(e, "client_name")),
            'bestell_nr': ft.Dropdown(label="Bestell-Nr.", on_change=lambda e: self.toggle_new_entry(e, "bestell_nr")),
            'bestelldatum': ft.TextField(label="Bestelldatum", visible=False),
            'baustelle': ft.Dropdown(label="Baustelle", on_change=lambda e: self.toggle_new_entry(e, "baustelle")),
            'anlagenteil': ft.Dropdown(label="Anlagenteil", on_change=lambda e: self.toggle_new_entry(e, "anlagenteil")),
            'aufmass_nr': ft.TextField(label="Aufmaß-Nr.", read_only=True, value=self.next_aufmass_nr),
            'auftrags_nr': ft.Dropdown(label="Auftrags-Nr.", on_change=lambda e: self.toggle_new_entry(e, "auftrags_nr")),
            'ausfuehrungsbeginn': ft.TextField(label="Ausführungsbeginn", visible=False),
            'ausfuehrungsende': ft.TextField(label="Ausführungsende", visible=False)
        }
        self.new_entry_fields = {
            key: ft.TextField(
                label=f"Neuer {value.label}",
                visible=False,
                on_change=lambda e, k=key: self.validate_number_field(e, k) if k in ["bestell_nr", "auftrags_nr"] else None
            ) 
            for key, value in self.invoice_detail_fields.items() 
            if key != 'aufmass_nr' and isinstance(value, ft.Dropdown)
        }
        # DatePickers
        self.create_date_pickers()

    def create_date_pickers(self):
        # DatePickers
        self.bestelldatum_picker = ft.DatePicker(
            on_change=self.on_bestelldatum_change,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31)
        )
        self.ausfuehrungsbeginn_picker = ft.DatePicker(
            on_change=self.on_ausfuehrungsbeginn_change,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31)
        )
        self.ausfuehrungsende_picker = ft.DatePicker(
            on_change=self.on_ausfuehrungsende_change,
            first_date=datetime(2024, 1, 1),
            last_date=datetime(2030, 12, 31)
        )
        self.page.overlay.extend([
            self.bestelldatum_picker,
            self.ausfuehrungsbeginn_picker,
            self.ausfuehrungsende_picker
        ])
        self.page.update()
        # Buttons to open DatePickers
        self.bestelldatum_button = ft.ElevatedButton(
            "Bestelldatum wählen",
            on_click=lambda _: self.bestelldatum_picker.pick_date()
        )
        self.ausfuehrungsbeginn_button = ft.ElevatedButton(
            "Ausführungsbeginn wählen",
            on_click=lambda _: self.ausfuehrungsbeginn_picker.pick_date()
        )
        self.ausfuehrungsende_button = ft.ElevatedButton(
            "Ausführungsende wählen",
            on_click=lambda _: self.ausfuehrungsende_picker.pick_date()
        )

    def load_last_invoice_data(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT client_name, bestell_nr, bestelldatum, baustelle, anlagenteil,
                       auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende
                FROM invoice
                ORDER BY id DESC
                LIMIT 1
            ''')
            last_invoice = cursor.fetchone()

            if last_invoice:
                self.invoice_detail_fields['client_name'].value = last_invoice[0]
                self.invoice_detail_fields['bestell_nr'].value = last_invoice[1]
                self.invoice_detail_fields['bestelldatum'].value = last_invoice[2]
                self.invoice_detail_fields['baustelle'].value = last_invoice[3]
                self.invoice_detail_fields['anlagenteil'].value = last_invoice[4]
                self.invoice_detail_fields['auftrags_nr'].value = last_invoice[5]
                self.invoice_detail_fields['ausfuehrungsbeginn'].value = last_invoice[6]
                self.invoice_detail_fields['ausfuehrungsende'].value = last_invoice[7]

                # Aktualisieren Sie die Datumspicker-Buttons
                self.update_date_picker_buttons()

            else:
                # Wenn keine vorherige Rechnung existiert, setzen Sie das heutige Datum
                today = datetime.now().strftime("%d.%m.%Y")
                self.invoice_detail_fields['bestelldatum'].value = today
                self.invoice_detail_fields['ausfuehrungsbeginn'].value = today
                self.invoice_detail_fields['ausfuehrungsende'].value = today
                self.update_date_picker_buttons()

        except sqlite3.Error as e:
            logging.error(f"Datenbankfehler beim Laden der letzten Rechnungsdaten: {str(e)}")
        finally:
            cursor.close()

    def update_date_picker_buttons(self):
        self.bestelldatum_button.text = f"Bestelldatum: {self.invoice_detail_fields['bestelldatum'].value}"
        self.ausfuehrungsbeginn_button.text = f"Ausführungsbeginn: {self.invoice_detail_fields['ausfuehrungsbeginn'].value}"
        self.ausfuehrungsende_button.text = f"Ausführungsende: {self.invoice_detail_fields['ausfuehrungsende'].value}"
        self.update()

    def create_article_input_fields(self):
        # Article input fields
        self.einheit_field = ft.TextField(label="Einheit", read_only=True, width=80)
        self.bauteil_dropdown = ft.Dropdown(label="Bauteil", on_change=self.update_dn_da_fields, width=220)
        self.dn_dropdown = ft.Dropdown(label="DN", on_change=self.update_dn_fields, width=80, options=[])
        self.da_dropdown = ft.Dropdown(label="DA", on_change=self.update_da_fields, width=80, options=[])
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=lambda e: update_price(self, e), width=140)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=lambda e: update_price(self, e), width=300)
        self.position_field = ft.TextField(label="Position", read_only=True, width=100)
        self.price_field = ft.TextField(label="Preis", read_only=True, width=80)
        self.quantity_input = ft.TextField(label="Menge", value="1", on_change=lambda e: update_price(self, e), width=80)
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True, width=150)
        
        # Sonderleistungen in neue Zeile verschoben und linksbündig ausgerichtet
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.show_sonderleistungen_dialog, width=200)
        self.sonderleistungen_row = ft.Row([self.sonderleistungen_button], alignment=ft.MainAxisAlignment.START)
        
        self.update_position_button = ft.ElevatedButton("Position aktualisieren", on_click=self.update_article_row, visible=False)
        # Category buttons
        self.category_buttons = [
            ft.ElevatedButton("Aufmaß", on_click=self.on_category_click, data="Aufmaß", width=150),
            ft.ElevatedButton("Material", on_click=self.on_category_click, data="Material", width=150),
            ft.ElevatedButton("Lohn", on_click=self.on_category_click, data="Lohn", width=150),
            ft.ElevatedButton("Festpreis", on_click=self.on_category_click, data="Festpreis", width=150)
        ]
        self.category_row = ft.Row(controls=self.category_buttons, spacing=1)

    def create_action_buttons(self):
        self.new_aufmass_button = ft.ElevatedButton(
            "Neues Aufmaß",
            on_click=self.reset_form,
            style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)
        )
        
        self.save_invoice_with_pdf_button = ft.ElevatedButton(
            "PDF mit Preisen erstellen",
            on_click=self.save_invoice_with_pdf,
            disabled=True
        )
        self.save_invoice_without_pdf_button = ft.ElevatedButton(
            "PDF ohne Preise erstellen",
            on_click=self.save_invoice_without_pdf,
            disabled=True
        )
        self.back_to_main_menu_button = ft.ElevatedButton(
            "Zurück zum Hauptmenü",
            on_click=self.back_to_main_menu
        )
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.show_zuschlaege_dialog, width=180)

    def create_article_list_table(self):
        # Article list table
        self.article_list_header = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Position")),
                ft.DataColumn(ft.Text("Bauteil")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Dämmdicke")),
                ft.DataColumn(ft.Text("Einheit")),
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Sonderleistungen")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen")),
            ],
            horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
            vertical_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
            heading_row_height=50,
            data_row_max_height=100,
            column_spacing=10,
        )

        # Einbetten der Tabelle in eine ListView
        self.scrollable_table = ft.ListView(
            [self.article_list_header],
            expand=1,
            spacing=10,
            padding=20,
            auto_scroll=True
        )

    def create_summary_fields(self):
        # Summary fields
        self.nettobetrag_field = ft.Text("0.00 €", size=16)
        self.zuschlaege_field = ft.Text("0.00 €", size=16)
        self.gesamtbetrag_field = ft.Text("0.00 €", size=18, weight=ft.FontWeight.BOLD)
        self.bemerkung_field = ft.TextField(
            label="Bemerkung",
            multiline=True,
            min_lines=3,
            max_lines=5
        )

    def build_invoice_details(self):
        # Build invoice details UI
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        self.invoice_detail_fields['client_name'],
                        self.new_entry_fields['client_name'],
                        self.invoice_detail_fields['baustelle'],
                        self.new_entry_fields['baustelle'],
                        self.invoice_detail_fields['anlagenteil'],
                        self.new_entry_fields['anlagenteil'],
                    ], expand=1),
                    ft.Column([
                        self.invoice_detail_fields['bestell_nr'],
                        self.new_entry_fields['bestell_nr'],
                        self.invoice_detail_fields['auftrags_nr'],
                        self.new_entry_fields['auftrags_nr'],
                        self.invoice_detail_fields['aufmass_nr'],
                    ], expand=1),
                ]),
                ft.Row([
                    ft.Column([
                        ft.Container(content=self.bestelldatum_button, alignment=ft.alignment.center),
                        self.invoice_detail_fields['bestelldatum'],
                    ], expand=1),
                    ft.Column([
                        ft.Container(content=self.ausfuehrungsbeginn_button, alignment=ft.alignment.center),
                        self.invoice_detail_fields['ausfuehrungsbeginn'],
                    ], expand=1),
                    ft.Column([
                        ft.Container(content=self.ausfuehrungsende_button, alignment=ft.alignment.center),
                        self.invoice_detail_fields['ausfuehrungsende'],
                    ], expand=1),
                ]),
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(bottom=20),
        )

    def build_article_input(self):
        # Entfernen Sie die Container-Wraps und passen Sie die Breiten an
        self.article_input_row = ft.Row([
            self.position_field,
            self.bauteil_dropdown,
            self.dn_dropdown,
            self.da_dropdown,
            self.dammdicke_dropdown,
            self.taetigkeit_dropdown,
            self.einheit_field,
            self.price_field,
            self.quantity_input,
            self.zwischensumme_field,
            ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
        ], alignment=ft.MainAxisAlignment.START, spacing=5, wrap=True)

        return ft.Container(
            content=ft.Column([
                ft.Text("Artikel hinzufügen", size=20, weight=ft.FontWeight.BOLD),
                self.article_input_row,
                self.sonderleistungen_row,
                self.update_position_button,
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(bottom=20),
        )


    def build_article_list(self):
        # Build article list UI
        return ft.Container(
            content=ft.Column([
                ft.Text("Artikelliste", size=20, weight=ft.FontWeight.BOLD),
                self.scrollable_table
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(bottom=20),
            expand=True,
        )

    def build_summary_and_actions(self):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        ft.Text("Nettobetrag:", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Zuschläge:", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Gesamtbetrag:", size=18, weight=ft.FontWeight.BOLD),
                    ], expand=1),
                    ft.Column([
                        self.nettobetrag_field,
                        self.zuschlaege_field,
                        self.gesamtbetrag_field,
                    ], expand=1, horizontal_alignment=ft.CrossAxisAlignment.END),
                ]),
                ft.Container(height=20),
                ft.Row([
                    self.zuschlaege_button,
                    self.save_invoice_with_pdf_button,
                    self.save_invoice_without_pdf_button,
                    self.new_aufmass_button,  # Verschoben nach rechts
                    self.back_to_main_menu_button,
                ], alignment=ft.MainAxisAlignment.CENTER),
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
        )

    def build_bemerkung_container(self):
        # Build bemerkung container
        return ft.Container(
            content=self.bemerkung_field,
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(bottom=20),
        )

    def get_next_aufmass_nr(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT MAX(id) FROM invoice")
            max_id = cursor.fetchone()[0]
            return str(max_id + 1) if max_id else "1"
        finally:
            cursor.close()

    def get_current_aufmass_nr(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_id = cursor.fetchone()[0]
            return str(max_id) if max_id else "0"
        finally:
            cursor.close()

    def load_invoice_options(self):
        for field in self.invoice_detail_fields:
            if field == 'aufmass_nr':
                continue
            options = self.get_from_cache_or_db(f"invoice_options_{field}", f"SELECT DISTINCT {field} FROM invoice WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
            self.invoice_detail_fields[field].options = [ft.dropdown.Option(str(option[0])) for option in options]
            self.invoice_detail_fields[field].options.append(ft.dropdown.Option("Neuer Eintrag"))

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    def load_data(self):
        # Load necessary data from the database
        self.load_faktoren("Sonderleistung")
        self.load_faktoren("Zuschläge")
        self.update_field_visibility()
        self.update_einheit()
        self.update_price()

    def load_faktoren(self, art):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
            faktoren = cursor.fetchall()
            if art == "Sonderleistung":
                self.sonderleistungen_options = [(bezeichnung, float(faktor)) for bezeichnung, faktor in faktoren]
            elif art == "Zuschläge":
                self.zuschlaege_options = [(bezeichnung, float(faktor)) for bezeichnung, faktor in faktoren]
        finally:
            cursor.close()

    def toggle_new_entry(self, e, field):
        dropdown = self.invoice_detail_fields[field]
        text_field = self.new_entry_fields[field]
        text_field.visible = dropdown.value == "Neuer Eintrag"
        self.update()

    def validate_number_field(self, e, field_name):
        value = e.control.value
        pattern = r'^[0-9-]*$'
        if not re.match(pattern, value):
            e.control.error_text = "Nur Zahlen und Bindestriche erlaubt"
        else:
            e.control.error_text = None
        self.update()

    def on_bestelldatum_change(self, e):
        self.update_date_field(e, 'bestelldatum', self.bestelldatum_button)

    def on_ausfuehrungsbeginn_change(self, e):
        self.update_date_field(e, 'ausfuehrungsbeginn', self.ausfuehrungsbeginn_button)

    def on_ausfuehrungsende_change(self, e):
        self.update_date_field(e, 'ausfuehrungsende', self.ausfuehrungsende_button)

    def update_date_field(self, e, field_name, button):
        if e.control.value:
            date_obj = e.control.value
            date_str = date_obj.strftime("%d.%m.%Y")
            self.invoice_detail_fields[field_name].value = date_str
            button.text = f"{self.invoice_detail_fields[field_name].label}: {date_str}"
        else:
            self.invoice_detail_fields[field_name].value = ""
            button.text = f"{self.invoice_detail_fields[field_name].label} wählen"
        self.update()

    def on_category_click(self, e):
        # Update category selection
        for button in self.category_buttons:
            button.style = None
        e.control.style = ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE)
        self.current_category = e.control.data
        load_items(self, self.current_category)
        self.update_field_visibility()
        self.update()

    def update_field_visibility(self):
        is_aufmass = self.current_category == "Aufmaß"
        self.dn_dropdown.visible = self.da_dropdown.visible = is_aufmass
        self.dammdicke_dropdown.visible = is_aufmass
        self.taetigkeit_dropdown.visible = is_aufmass
        self.update()

    def update_dn_da_fields(self, e):
        bauteil = self.bauteil_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            self.auto_fill_rohrleitung_or_formteil(bauteil)
        else:
            self.dn_dropdown.visible = False
            self.da_dropdown.visible = False
            self.dn_dropdown.value = None
            self.da_dropdown.value = None
        self.update_dammdicke_options()
        self.update_einheit()
        update_price(self)
        self.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ? LIMIT 1', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def auto_fill_rohrleitung_or_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT DN FROM price_list WHERE Bauteil = "Rohrleitung" ORDER BY DN')
            dn_options = [row[0] for row in cursor.fetchall()]
            self.dn_dropdown.options = [ft.dropdown.Option(str(int(dn))) for dn in dn_options]
            self.dn_dropdown.value = str(int(dn_options[0]))

            cursor.execute('SELECT DISTINCT DA FROM price_list WHERE Bauteil = "Rohrleitung" ORDER BY DA')
            da_options = [row[0] for row in cursor.fetchall()]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]

            cursor.execute('SELECT MIN(DA) FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ?', (dn_options[0],))
            first_valid_da = cursor.fetchone()[0]
            self.da_dropdown.value = str(first_valid_da)

            self.dn_dropdown.visible = True
            self.da_dropdown.visible = True

            self.update_dammdicke_options()
            if self.dammdicke_dropdown.options:
                self.dammdicke_dropdown.value = self.dammdicke_dropdown.options[0].key

            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung LIMIT 1')
            first_taetigkeit = cursor.fetchone()[0]
            self.taetigkeit_dropdown.value = first_taetigkeit

            update_price(self)
        finally:
            cursor.close()

    def update_einheit(self):
        bauteil = self.bauteil_dropdown.value
        if bauteil:
            if self.is_formteil(bauteil):
                self.einheit_field.value = "m²"
            else:
                cursor = self.conn.cursor()
                try:
                    cursor.execute('SELECT Unit FROM price_list WHERE Bauteil = ? LIMIT 1', (bauteil,))
                    result = cursor.fetchone()
                    if result:
                        self.einheit_field.value = result[0]
                    else:
                        self.einheit_field.value = ""
                finally:
                    cursor.close()
        else:
            self.einheit_field.value = ""
        self.update()

    def update_dn_fields(self, e):
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT MIN(DA) FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ?', (dn,))
                first_valid_da = cursor.fetchone()[0]
                if first_valid_da:
                    self.da_dropdown.value = str(first_valid_da)
                else:
                    self.da_dropdown.value = None
            finally:
                cursor.close()
        self.update_dammdicke_options()
        update_price(self)
        self.update()

    def update_da_fields(self, e):
        bauteil = self.bauteil_dropdown.value
        da = self.da_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            cursor = self.conn.cursor()
            try:
                cursor.execute('SELECT MIN(DN) FROM price_list WHERE Bauteil = "Rohrleitung" AND DA = ?', (da,))
                first_valid_dn = cursor.fetchone()[0]
                if first_valid_dn:
                    self.dn_dropdown.value = str(int(first_valid_dn))
                else:
                    self.dn_dropdown.value = None
            finally:
                cursor.close()
        self.update_dammdicke_options()
        update_price(self)
        self.update()

    def update_dammdicke_options(self):
        bauteil = self.bauteil_dropdown.value
        if not bauteil:
            return
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke_options = get_dammdicke_options(self, bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        if dammdicke_options:
            self.dammdicke_dropdown.value = str(dammdicke_options[0])
        else:
            self.dammdicke_dropdown.value = None
        self.dammdicke_dropdown.update()

    def update_price(self, e=None):
        update_price(self)

    def add_article_row(self, e):
        logging.info("Starte add_article_row Methode")

        if not self.bauteil_dropdown.value:
            self.show_error("Bitte wählen Sie ein Bauteil aus.")
            logging.warning("Kein Bauteil ausgewählt")
            return

        if not self.quantity_input.value or float(self.quantity_input.value) <= 0:
            self.show_error("Bitte geben Sie eine gültige Menge ein.")
            logging.warning("Ungültige Menge")
            return

        if not self.price_field.value or float(self.price_field.value.replace(',', '.')) <= 0:
            self.show_error("Bitte geben Sie einen gültigen Preis ein.")
            logging.warning("Ungültiger Preis")
            return

        if not self.zwischensumme_field.value or float(self.zwischensumme_field.value.replace(',', '.')) <= 0:
            self.show_error("Bitte berechnen Sie die Zwischensumme.")
            logging.warning("Ungültige Zwischensumme")
            return

        # Erstellen Sie einen eindeutigen Identifikator für den Artikel
        neuer_artikel_id = (
            self.bauteil_dropdown.value,
            self.dn_dropdown.value if self.dn_dropdown.visible else "",
            self.da_dropdown.value if self.da_dropdown.visible else "",
            self.dammdicke_dropdown.value,
            self.taetigkeit_dropdown.value,
            ", ".join([sl[0] for sl in self.selected_sonderleistungen])
        )
        logging.info(f"Neuer Artikel ID: {neuer_artikel_id}")

        # Prüfen Sie, ob dieser Artikel bereits in der Liste ist
        for index, row in enumerate(self.article_list_header.rows):
            existing_artikel_id = (
                row.cells[1].content.value,  # Bauteil
                row.cells[2].content.value,  # DN
                row.cells[3].content.value,  # DA
                row.cells[4].content.value,  # Dämmdicke
                row.cells[6].content.value,  # Tätigkeit
                row.cells[7].content.value,  # Sonderleistungen
            )
            logging.info(f"Vergleiche mit existierendem Artikel {index}: {existing_artikel_id}")
            if neuer_artikel_id == existing_artikel_id:
                error_message = "Dieser Artikel ist bereits in der Liste vorhanden."
                logging.warning(error_message)
                self.show_error(error_message)
                self.page.update()
                return

        logging.info("Füge neuen Artikel hinzu")
        # Wenn der Artikel noch nicht in der Liste ist, fügen Sie ihn hinzu
        position = self.position_field.value
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else ""
        da = self.da_dropdown.value if self.da_dropdown.visible else ""
        dammdicke = self.dammdicke_dropdown.value
        einheit = self.einheit_field.value
        taetigkeit = self.taetigkeit_dropdown.value
        menge = self.quantity_input.value
        preis = self.price_field.value
        sonderleistungen = ", ".join([sl[0] for sl in self.selected_sonderleistungen])
        zwischensumme = self.zwischensumme_field.value

        new_row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(position, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(bauteil, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(dn, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(da, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(dammdicke, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(einheit, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(taetigkeit, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(sonderleistungen, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(preis, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(menge, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(ft.Text(zwischensumme, text_align=ft.TextAlign.CENTER)),
                ft.DataCell(
                    ft.Row([
                        ft.IconButton(
                            icon=ft.icons.EDIT,
                            icon_color="blue500",
                            on_click=lambda _, row=len(self.article_list_header.rows): self.edit_article_row(row)
                        ),
                        ft.IconButton(
                            icon=ft.icons.DELETE,
                            icon_color="red500",
                            on_click=lambda _, row=len(self.article_list_header.rows): self.delete_article_row(row)
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER)
                )
            ]
        )
        self.article_list_header.rows.append(new_row)

        summary_data = {
            'zwischensumme': float(zwischensumme.replace(',', '.')),
            'sonderleistungen': self.selected_sonderleistungen.copy()
        }
        self.article_summaries.append(summary_data)

        self.update_total_price()
        self.clear_input_fields()
        self.update_pdf_buttons()
        self.page.update()
        logging.info(f"Neue Artikelzeile hinzugefügt: {position}")

    def edit_article_row(self, row_index):
        if 0 <= row_index < len(self.article_list_header.rows):
            row = self.article_list_header.rows[row_index]
            self.edit_mode = True
            self.edit_row_index = row_index
            self.update_position_button.visible = True

            # Fill the input fields with values from the selected row
            self.position_field.value = row.cells[0].content.value
            self.bauteil_dropdown.value = row.cells[1].content.value
            self.dn_dropdown.value = row.cells[2].content.value
            self.da_dropdown.value = row.cells[3].content.value
            self.dammdicke_dropdown.value = row.cells[4].content.value
            self.einheit_field.value = row.cells[5].content.value
            self.taetigkeit_dropdown.value = row.cells[6].content.value

            # Handle sonderleistungen
            sonderleistungen_str = row.cells[7].content.value
            self.selected_sonderleistungen = []
            if sonderleistungen_str:
                sonderleistungen = sonderleistungen_str.split(', ')
                for sl in sonderleistungen:
                    faktor = self.get_sonderleistung_faktor(sl)
                    self.selected_sonderleistungen.append((sl, faktor))

            self.price_field.value = row.cells[8].content.value.replace(' €', '')
            self.quantity_input.value = row.cells[9].content.value
            self.zwischensumme_field.value = row.cells[10].content.value.replace(' €', '')

            self.update_sonderleistungen_button()
            self.update()
        else:
            logging.warning(f"Ungültiger Zeilenindex beim Bearbeiten: {row_index}")

    def update_article_row(self, e):
        if self.edit_mode and self.edit_row_index is not None:
            if 0 <= self.edit_row_index < len(self.article_list_header.rows):
                sonderleistungen = ", ".join([sl[0] for sl in self.selected_sonderleistungen])
                updated_row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(self.position_field.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.bauteil_dropdown.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "", text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "", text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.dammdicke_dropdown.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.einheit_field.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.taetigkeit_dropdown.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(sonderleistungen, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.price_field.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.quantity_input.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(ft.Text(self.zwischensumme_field.value, text_align=ft.TextAlign.CENTER)),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_color="blue500",
                                    on_click=lambda _, row=self.edit_row_index: self.edit_article_row(row)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color="red500",
                                    on_click=lambda _, row=self.edit_row_index: self.delete_article_row(row)
                                )
                            ], alignment=ft.MainAxisAlignment.CENTER)
                        )
                    ]
                )

                self.article_list_header.rows[self.edit_row_index] = updated_row
                self.article_summaries[self.edit_row_index] = {
                    'zwischensumme': float(self.zwischensumme_field.value.replace(',', '.')),
                    'sonderleistungen': self.selected_sonderleistungen.copy()
                }

                self.edit_mode = False
                self.edit_row_index = None
                self.update_position_button.visible = False
                self.clear_input_fields()
                self.update_total_price()
                self.update()
                logging.info(f"Artikelzeile {self.edit_row_index} aktualisiert")
            else:
                logging.warning(f"Ungültiger Zeilenindex beim Aktualisieren: {self.edit_row_index}")
                self.show_error("Die zu bearbeitende Zeile wurde möglicherweise gelöscht. Bitte versuchen Sie es erneut.")
                self.edit_mode = False
                self.edit_row_index = None
                self.update_position_button.visible = False
                self.clear_input_fields()
                self.update()
        else:
            logging.warning("Versuch, eine Zeile zu aktualisieren, ohne im Bearbeitungsmodus zu sein")

    def get_sonderleistung_faktor(self, sonderleistung):
        for sl, faktor in self.sonderleistungen_options:
            if sl == sonderleistung:
                return faktor
        return 1.0  # Standardfaktor, falls nicht gefunden

    def is_rohrleitung(self, bauteil):
        return bauteil.lower() == "rohrleitung"

    def back_to_main_menu(self, e):
        self.page.go('/')

    def reset_form(self, e):
        # Behalten Sie die Kopfdaten bei
        kopfdaten = {
            'client_name': self.invoice_detail_fields['client_name'].value,
            'bestell_nr': self.invoice_detail_fields['bestell_nr'].value,
            'bestelldatum': self.invoice_detail_fields['bestelldatum'].value,
            'baustelle': self.invoice_detail_fields['baustelle'].value,
            'anlagenteil': self.invoice_detail_fields['anlagenteil'].value,
            'auftrags_nr': self.invoice_detail_fields['auftrags_nr'].value,
            'ausfuehrungsbeginn': self.invoice_detail_fields['ausfuehrungsbeginn'].value,
            'ausfuehrungsende': self.invoice_detail_fields['ausfuehrungsende'].value,
        }

        # Setzen Sie die Aufmaß-Nummer zurück
        self.next_aufmass_nr = self.get_next_aufmass_nr()
        self.invoice_detail_fields['aufmass_nr'].value = self.next_aufmass_nr

        # Setzen Sie alle anderen Felder zurück
        self.clear_input_fields()
        self.article_list_header.rows.clear()
        self.article_summaries.clear()
        self.selected_sonderleistungen.clear()
        self.selected_zuschlaege.clear()
        self.bemerkung_field.value = ""

        # Setzen Sie die Kopfdaten wieder ein
        for field, value in kopfdaten.items():
            self.invoice_detail_fields[field].value = value

        # Aktualisieren Sie die Gesamtpreise
        self.update_total_price()
        self.update_pdf_buttons()

        # Aktualisieren Sie die Benutzeroberfläche
        self.update()
        self.show_snack_bar("Neues Aufmaß erstellt. Kopfdaten wurden beibehalten.")

    def show_sonderleistungen_dialog(self, e):
        dialog = ft.AlertDialog(
            title=ft.Text("Sonderleistungen auswählen"),
            content=ft.Column([
                ft.Checkbox(
                    label=sl[0],
                    value=sl[0] in [s[0] for s in self.selected_sonderleistungen],
                    on_change=lambda e, sl=sl: self.on_sonderleistung_change(e, sl[0], sl[1])
                ) for sl in self.sonderleistungen_options
            ], scroll=ft.ScrollMode.AUTO, height=300),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_sonderleistungen_dialog(dialog))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def on_sonderleistung_change(self, e, sonderleistung, faktor):
        checkbox = e.control
        if checkbox.value:
            if not any(sl[0] == sonderleistung for sl in self.selected_sonderleistungen):
                self.selected_sonderleistungen.append((sonderleistung, faktor))
        else:
            self.selected_sonderleistungen = [sl for sl in self.selected_sonderleistungen if sl[0] != sonderleistung]
        self.update_price()
        self.update_sonderleistungen_button()
        self.page.update()

    def close_sonderleistungen_dialog(self, dialog):
        dialog.open = False
        self.page.update()
        self.update_sonderleistungen_button()

    def update_sonderleistungen_button(self):
        count = len(self.selected_sonderleistungen)
        self.sonderleistungen_button.text = f"Sonderleistungen ({count})"
        self.update()

    def save_invoice_with_pdf(self, e):
        self.create_pdf(include_prices=True)

    def save_invoice_without_pdf(self, e):
        self.create_pdf(include_prices=False)

    def create_pdf(self, include_prices=True):
        logging.info("Starte PDF-Erstellung")
        is_valid, error_message = self.validate_invoice_details()
        if not is_valid:
            self.show_snack_bar(error_message)
            return

        try:
            invoice_data = self.get_invoice_data()
            invoice_data['bemerkungen'] = self.bemerkung_field.value
            logging.info(f"Rechnungsdaten erhalten: {invoice_data}")

            invoice_id = self.save_invoice_to_db(invoice_data)
            if invoice_id is None:
                raise Exception("Fehler beim Speichern der Rechnung in der Datenbank")

            # Überprüfen, ob bereits eine PDF für diese Rechnung existiert
            existing_pdf = self.check_existing_pdf(invoice_id)
            if existing_pdf:
                self.show_snack_bar(f"Bestehende PDF aktualisiert: {existing_pdf}")
                return

            filename = f"Rechnung_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf" if include_prices else f"Auftragsbestätigung_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(os.path.expanduser("~"), "Downloads", filename)
            logging.info(f"Versuche PDF zu erstellen: {filepath}")

            if not os.path.exists(os.path.dirname(filepath)):
                logging.warning(f"Zielordner existiert nicht: {os.path.dirname(filepath)}")
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                logging.info(f"Zielordner erstellt: {os.path.dirname(filepath)}")

            generate_pdf(invoice_data, filepath, include_prices=include_prices)

            if os.path.exists(filepath):
                logging.info(f"PDF erfolgreich erstellt: {filepath}")
                self.show_snack_bar(f"PDF wurde erstellt: {filepath}")
                self.pdf_generated = True
                self.update_pdf_buttons()
            else:
                raise FileNotFoundError(f"PDF-Datei wurde nicht erstellt: {filepath}")

        except Exception as ex:
            logging.error(f"Fehler beim Erstellen des PDFs: {str(ex)}", exc_info=True)
            self.show_snack_bar(f"Fehler beim Erstellen des PDFs: {str(ex)}")

    def check_existing_pdf(self, invoice_id):
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        for filename in os.listdir(downloads_dir):
            if filename.startswith(f"Rechnung_{invoice_id}_") or filename.startswith(f"Auftragsbestätigung_{invoice_id}_"):
                return os.path.join(downloads_dir, filename)
        return None

    def show_zuschlaege_dialog(self, e):
        dialog = ft.AlertDialog(
            title=ft.Text("Zuschläge auswählen"),
            content=ft.Column([
                ft.Checkbox(
                    label=z[0],
                    value=z[0] in [s[0] for s in self.selected_zuschlaege],
                    on_change=lambda e, z=z: self.toggle_zuschlag(e, z[0], z[1])
                ) for z in self.zuschlaege_options
            ], scroll=ft.ScrollMode.AUTO, height=300),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_zuschlaege_dialog(dialog))
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
        self.update_zuschlaege_button()

    def toggle_zuschlag(self, e, bezeichnung, faktor):
        if e.control.value:
            self.selected_zuschlaege.append((bezeichnung, faktor))
        else:
            self.selected_zuschlaege = [item for item in self.selected_zuschlaege if item[0] != bezeichnung]
        self.update_total_price()
        self.update()

    def close_zuschlaege_dialog(self, dialog):
        dialog.open = False
        self.page.update()
        self.update_zuschlaege_button()

    def update_zuschlaege_button(self):
        count = len(self.selected_zuschlaege)
        self.zuschlaege_button.text = f"Zuschläge ({count})"
        self.update()

    def update_total_price(self):
        logging.info("Starte Aktualisierung des Gesamtpreises")
        try:
            nettobetrag = sum(
                float(row.cells[10].content.value.replace(',', '.').replace('€', '').strip() or '0')
                for row in self.article_list_header.rows
            )
            logging.info(f"Berechneter Nettobetrag: {nettobetrag}")

            zuschlaege_summe = 0
            for bezeichnung, faktor in self.selected_zuschlaege:
                zuschlag = nettobetrag * (float(faktor) - 1)
                zuschlaege_summe += zuschlag
                logging.info(f"Zuschlag '{bezeichnung}': {zuschlag:.2f}")

            gesamtbetrag = nettobetrag + zuschlaege_summe
            logging.info(f"Gesamtbetrag nach Zuschlägen: {gesamtbetrag}")

            self.nettobetrag_field.value = f"{nettobetrag:.2f} €"
            self.zuschlaege_field.value = f"{zuschlaege_summe:.2f} €"
            self.gesamtbetrag_field.value = f"{gesamtbetrag:.2f} €"
            self.update()
        except Exception as e:
            logging.error(f"Fehler bei der Aktualisierung des Gesamtpreises: {str(e)}")
            logging.exception(e)

    def show_error(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.colors.RED_400)
        self.page.snack_bar.open = True
        self.update()

    def clear_input_fields(self):
        self.position_field.value = ""
        self.bauteil_dropdown.value = None
        self.dn_dropdown.value = None
        self.da_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.einheit_field.value = ""
        self.price_field.value = ""
        self.quantity_input.value = "1"
        self.zwischensumme_field.value = ""
        self.selected_sonderleistungen = []
        self.update_sonderleistungen_button()
        self.update()

    def delete_article_row(self, row_index):
        if 0 <= row_index < len(self.article_list_header.rows):
            del self.article_list_header.rows[row_index]
            del self.article_summaries[row_index]

            if self.edit_mode and self.edit_row_index is not None:
                if row_index < self.edit_row_index:
                    self.edit_row_index -= 1
                elif row_index == self.edit_row_index:
                    self.edit_mode = False
                    self.edit_row_index = None
                    self.update_position_button.visible = False
                    self.clear_input_fields()

            self.update_total_price()
            self.update_pdf_buttons()
            self.update()
            logging.info(f"Artikelzeile {row_index} gelöscht")
        else:
            logging.warning(f"Ungültiger Zeilenindex beim Löschen: {row_index}")

    def update_pdf_buttons(self):
        has_articles = len(self.article_list_header.rows) > 0
        logging.info(f"Updating PDF buttons. Has articles: {has_articles}")
        if self.pdf_generated:
            self.save_invoice_with_pdf_button.text = "Rechnung aktualisiert speichern (mit PDF)"
            self.save_invoice_without_pdf_button.text = "Rechnung aktualisiert speichern (ohne PDF)"
        self.save_invoice_with_pdf_button.disabled = not has_articles
        self.save_invoice_without_pdf_button.disabled = not has_articles
        self.update()

    def validate_invoice_details(self):
        required_fields = [
            'client_name', 'bestell_nr', 'bestelldatum', 'baustelle', 'anlagenteil',
            'auftrags_nr', 'ausfuehrungsbeginn', 'ausfuehrungsende'
        ]

        for field in required_fields:
            value = self.invoice_detail_fields[field].value
            if value is None or value == "" or value == "Neuer Eintrag":
                if self.new_entry_fields.get(field) and self.new_entry_fields[field].visible and self.new_entry_fields[field].value:
                    continue
                return False, f"Bitte füllen Sie das Feld '{self.invoice_detail_fields[field].label}' aus."

        return True, ""

    def show_snack_bar(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

    def get_invoice_data(self):
        logging.info("Sammle Rechnungsdaten")
        invoice_data = {
            'client_name': self.invoice_detail_fields['client_name'].value if self.invoice_detail_fields['client_name'].value != "Neuer Eintrag" else self.new_entry_fields['client_name'].value,
            'bestell_nr': self.invoice_detail_fields['bestell_nr'].value if self.invoice_detail_fields['bestell_nr'].value != "Neuer Eintrag" else self.new_entry_fields['bestell_nr'].value,
            'bestelldatum': self.invoice_detail_fields['bestelldatum'].value,
            'baustelle': self.invoice_detail_fields['baustelle'].value if self.invoice_detail_fields['baustelle'].value != "Neuer Eintrag" else self.new_entry_fields['baustelle'].value,
            'anlagenteil': self.invoice_detail_fields['anlagenteil'].value if self.invoice_detail_fields['anlagenteil'].value != "Neuer Eintrag" else self.new_entry_fields['anlagenteil'].value,
            'aufmass_nr': self.next_aufmass_nr,
            'auftrags_nr': self.invoice_detail_fields['auftrags_nr'].value if self.invoice_detail_fields['auftrags_nr'].value != "Neuer Eintrag" else self.new_entry_fields['auftrags_nr'].value,
            'ausfuehrungsbeginn': self.invoice_detail_fields['ausfuehrungsbeginn'].value,
            'ausfuehrungsende': self.invoice_detail_fields['ausfuehrungsende'].value,
            'category': self.current_category,
            'bemerkung': self.bemerkung_field.value,
            'zuschlaege': self.selected_zuschlaege,
            'articles': [],
            'net_total': 0,
            'total_price': 0
        }

        for row in self.article_list_header.rows:
            article = {
                'position': row.cells[0].content.value,
                'artikelbeschreibung': row.cells[1].content.value,
                'dn': row.cells[2].content.value,
                'da': row.cells[3].content.value,
                'dammdicke': row.cells[4].content.value,
                'einheit': row.cells[5].content.value,
                'taetigkeit': row.cells[6].content.value,
                'sonderleistungen': row.cells[7].content.value,
                'einheitspreis': row.cells[8].content.value,
                'quantity': row.cells[9].content.value,
                'zwischensumme': row.cells[10].content.value
            }
            invoice_data['articles'].append(article)
            try:
                zwischensumme = float(article['zwischensumme'].replace(',', '.').replace('€', '').strip())
                invoice_data['net_total'] += zwischensumme
            except ValueError:
                logging.warning(f"Ungültiger Zwischensummenwert: {article['zwischensumme']}")

        total_price = invoice_data['net_total']
        for _, faktor in invoice_data['zuschlaege']:
            total_price *= float(faktor)

        invoice_data['total_price'] = total_price

        logging.info(f"Gesammelte Rechnungsdaten: {invoice_data}")
        return invoice_data

    def save_invoice_to_db(self, invoice_data):
        logging.info("Speichere Rechnung in der Datenbank")
        logging.debug(f"Rechnungsdaten: {invoice_data}")

        nettobetrag = sum(float(article['zwischensumme'].replace(',', '.').replace('€', '').strip()) for article in invoice_data['articles'])
        zuschlaege_summe = 0
        for zuschlag, faktor in invoice_data['zuschlaege']:
            zuschlag_betrag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag_betrag
        total_price = nettobetrag + zuschlaege_summe

        cursor = self.conn.cursor()
        try:
            # Prüfen, ob bereits eine Rechnung mit dieser Aufmaß-Nummer existiert
            cursor.execute('SELECT id, aufmass_nr FROM invoice WHERE aufmass_nr = ?', (self.invoice_detail_fields['aufmass_nr'].value,))
            existing_invoice = cursor.fetchone()

            if existing_invoice:
                # Wenn eine Rechnung mit dieser Nummer existiert, aktualisieren wir sie
                invoice_id, existing_aufmass_nr = existing_invoice
                cursor.execute('''
                UPDATE invoice SET
                    client_name = ?, bestell_nr = ?, bestelldatum = ?, baustelle = ?, anlagenteil = ?,
                    auftrags_nr = ?, ausfuehrungsbeginn = ?, ausfuehrungsende = ?,
                    total_amount = ?, zuschlaege = ?, bemerkungen = ?
                WHERE id = ?
                ''', (
                    invoice_data['client_name'],
                    invoice_data['bestell_nr'],
                    invoice_data['bestelldatum'],
                    invoice_data['baustelle'],
                    invoice_data['anlagenteil'],
                    invoice_data['auftrags_nr'],
                    invoice_data['ausfuehrungsbeginn'],
                    invoice_data['ausfuehrungsende'],
                    total_price,
                    ','.join([f"{z[0]}:{z[1]}" for z in invoice_data['zuschlaege']]),
                    invoice_data.get('bemerkungen', ''),
                    invoice_id
                ))

                # Löschen der alten Artikel für diese Rechnung
                cursor.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (invoice_id,))
            else:
                # Wenn keine Rechnung mit dieser Nummer existiert, erstellen wir eine neue
                cursor.execute('SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice')
                max_aufmass_nr = cursor.fetchone()[0]
                new_aufmass_nr = str(int(max_aufmass_nr or 0) + 1)
                
                cursor.execute('''
                INSERT INTO invoice (
                    client_name, bestell_nr, bestelldatum, baustelle, anlagenteil,
                    aufmass_nr, auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende,
                    total_amount, zuschlaege, bemerkungen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_data['client_name'],
                    invoice_data['bestell_nr'],
                    invoice_data['bestelldatum'],
                    invoice_data['baustelle'],
                    invoice_data['anlagenteil'],
                    new_aufmass_nr,
                    invoice_data['auftrags_nr'],
                    invoice_data['ausfuehrungsbeginn'],
                    invoice_data['ausfuehrungsende'],
                    total_price,
                    ','.join([f"{z[0]}:{z[1]}" for z in invoice_data['zuschlaege']]),
                    invoice_data.get('bemerkungen', '')
                ))
                invoice_id = cursor.lastrowid
                self.invoice_detail_fields['aufmass_nr'].value = new_aufmass_nr

            # Fügen Sie die Artikel für diese Rechnung hinzu
            for article in invoice_data['articles']:
                cursor.execute('''
                    INSERT INTO invoice_items (invoice_id, position, Bauteil, DN, DA, Size, taetigkeit, Unit, Value, quantity, zwischensumme, sonderleistungen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id,
                    article['position'],
                    article['artikelbeschreibung'],
                    article.get('dn', ''),
                    article.get('da', ''),
                    article.get('dammdicke', ''),
                    article.get('taetigkeit', ''),
                    article.get('einheit', ''),
                    article.get('einheitspreis', 0),
                    article.get('quantity', 0),
                    article.get('zwischensumme', 0),
                    str(article.get('sonderleistungen', ''))
                ))

            self.conn.commit()
            logging.info(f"Rechnung mit ID {invoice_id} erfolgreich in der Datenbank gespeichert")
            return invoice_id
        except sqlite3.Error as e:
            logging.error(f"Datenbankfehler beim Speichern der Rechnung: {str(e)}")
            self.conn.rollback()
            raise Exception(f"Datenbankfehler: {str(e)}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Speichern der Rechnung: {str(e)}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()