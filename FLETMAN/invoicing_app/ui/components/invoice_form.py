import logging
import sqlite3
import flet as ft
import re
import os
from datetime import datetime

from database.db_operations import get_db_connection
from .invoice_pdf_generator import generate_pdf
from .invoice_form_helpers import (
    load_aufmass_items, load_items, load_faktoren, get_all_dn_options,
    get_all_da_options, get_dammdicke_options, get_base_price,
    get_material_price, get_taetigkeit_faktor, get_positionsnummer, update_price,
    load_material_items, load_lohn_items, load_festpreis_items
)

class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        logging.info("Initializing InvoiceForm")
        self.conn = get_db_connection()
        self.next_aufmass_nr = self.get_next_aufmass_nr()
        
        # Überprüfen Sie den Datenbankinhalt
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM price_list")
        count = cursor.fetchone()[0]
        logging.info(f"Number of items in price_list: {count}")
        cursor.close()
        
        self.cache = {}
        self.article_summaries = []
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        self.previous_bauteil = None
        self.current_category = "Aufmaß"  # Setzen Sie eine Standardkategorie
        self.edit_mode = False
        self.edit_row_index = None
        self.update_position_button = ft.ElevatedButton("Position aktualisieren", on_click=self.update_article_row, visible=False)
        self.article_count = 0
        
        # Sonderleistungen
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen, width=150)
        self.sonderleistungen_container = ft.Container(
        content=ft.Column(controls=[]),
            visible=False,
            expand=True  # Dies könnte helfen, den Container sichtbarer zu machen
        )
        self.create_sonderleistungen_checkboxes()

        # Zuschläge
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege)
        self.zuschlaege_container = ft.Container(visible=False)
        self.create_zuschlaege_checkboxes()
        
        logging.info("Creating UI elements")
        self.create_ui_elements()
        self.load_invoice_options()
        logging.info("Loading data")
        self.load_data()
        load_items(self, self.current_category)  # Laden Sie die Items basierend auf der Standardkategorie
        self.update_price()  # Initialisieren Sie die Preisberechnung
        logging.info("InvoiceForm initialization complete")

        self.create_pdf_with_prices_button = ft.ElevatedButton(
            "PDF mit Preisen erstellen",
            on_click=self.create_pdf_with_prices,
            disabled=True
        )
        self.create_pdf_without_prices_button = ft.ElevatedButton(
            "PDF ohne Preise erstellen",
            on_click=self.create_pdf_without_prices,
            disabled=True
        )

    def create_sonderleistungen_checkboxes(self):
        sonderleistungen = self.load_sonderleistungen_from_db()
        checkboxes = [ft.Checkbox(label=sl, value=False) for sl in sonderleistungen]
        self.sonderleistungen_container.content = ft.Column(controls=checkboxes)

    def create_zuschlaege_checkboxes(self):
        zuschlaege = self.load_zuschlaege_from_db()
        checkboxes = [ft.Checkbox(label=f"{z[0]} ({z[1]})", value=False) for z in zuschlaege]
        self.zuschlaege_container.content = ft.Column(controls=checkboxes)

    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        self.page.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.page.update()

    

    def load_sonderleistungen_from_db(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Sonderleistung"')
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def load_zuschlaege_from_db(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = "Zuschlag"')
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_next_aufmass_nr(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT MAX(id) FROM invoice")
            max_id = cursor.fetchone()[0]
            return str(max_id + 1) if max_id else "1"
        finally:
            cursor.close()

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

    def build(self):
        logging.info("Building InvoiceForm UI")
        
        # Vergrößere und zentriere die Datumsbuttons
        for button in [self.bestelldatum_button, self.ausfuehrungsbeginn_button, self.ausfuehrungsende_button]:
            button.width = 250
            button.height = 50
            button.alignment = ft.alignment.center

        # 3x3 Kopfdaten-Layout
        invoice_details = ft.Column([
            ft.Row([
                ft.Column([self.invoice_detail_fields['client_name'], self.new_entry_fields['client_name']], expand=1),
                ft.Column([self.invoice_detail_fields['bestell_nr'], self.new_entry_fields['bestell_nr']], expand=1),
                ft.Column([self.invoice_detail_fields['aufmass_nr']], expand=1),
            ]),
            ft.Row([
                ft.Column([self.invoice_detail_fields['baustelle'], self.new_entry_fields['baustelle']], expand=1),
                ft.Column([self.invoice_detail_fields['anlagenteil'], self.new_entry_fields['anlagenteil']], expand=1),
                ft.Column([self.invoice_detail_fields['auftrags_nr'], self.new_entry_fields['auftrags_nr']], expand=1),
            ]),
            ft.Row([
                ft.Column([ft.Container(content=self.bestelldatum_button, alignment=ft.alignment.center), self.invoice_detail_fields['bestelldatum']], expand=1),
                ft.Column([ft.Container(content=self.ausfuehrungsbeginn_button, alignment=ft.alignment.center), self.invoice_detail_fields['ausfuehrungsbeginn']], expand=1),
                ft.Column([ft.Container(content=self.ausfuehrungsende_button, alignment=ft.alignment.center), self.invoice_detail_fields['ausfuehrungsende']], expand=1),
            ]),
        ])

        # Logo hinzufügen
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                             'assets', 'logos', 'KAE_Logo_RGB_300dpi2.jpg')
        logo = ft.Image(src=logo_path, width=100, height=50)
        logo_container = ft.Container(content=logo)

        # Verstecke die Kategorie-Buttons
        for button in self.category_buttons:
            button.visible = False

        # Bemerkungsfeld und die drei Felder nebeneinander
        bottom_row = ft.Row([
            ft.Container(
                content=self.bemerkung_field,
                width=self.page.width * 0.5 if self.page.width else 300
            ),
            ft.Container(width=20),  # Abstand
            self.nettobetrag_field,
            self.zuschlaege_field,
            self.gesamtbetrag_field
        ])

        # Restliches Layout
        main_content = ft.Column([
            ft.Row([logo_container], alignment=ft.MainAxisAlignment.END),
            invoice_details,
            ft.Container(height=20),
            self.category_row,
            self.article_input_row,  # Fügen Sie den Button separat hinzu
            self.sonderleistungen_container,
            self.article_list_header,
            self.article_list,
            bottom_row,
            ft.Row([
                self.zuschlaege_button,
                self.create_pdf_with_prices_button,
                self.create_pdf_without_prices_button,
                self.back_to_main_menu_button
            ], alignment=ft.MainAxisAlignment.END),
            self.zuschlaege_container,
        ])

        return ft.Container(
            content=main_content,
            padding=10,
            expand=True
        )


    def show_snack_bar(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

    def on_zuschlag_change(self, e):
        checkbox = e.control
        bezeichnung = checkbox.label
        if checkbox.value:
            faktor = self.get_zuschlag_faktor(bezeichnung)
            self.selected_zuschlaege.append((bezeichnung, faktor))
        else:
            self.selected_zuschlaege = [(b, f) for b, f in self.selected_zuschlaege if b != bezeichnung]
        self.update_total_price()

    def get_zuschlag_faktor(self, bezeichnung):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Zuschlag" AND Bezeichnung = ?', (bezeichnung,))
            result = cursor.fetchone()
            return result[0] if result else 1.0
        finally:
            cursor.close()

    def create_ui_elements(self):
        # Definieren Sie einheit_field am Anfang der Methode
        self.einheit_field = ft.TextField(label="Einheit", read_only=True, width=80)

        # Änderung hier: Umbenennung von artikelbeschreibung_dropdown zu bauteil_dropdown
        self.bauteil_dropdown = ft.Dropdown(label="Bauteil", on_change=self.update_dn_da_fields, width=250)
        # Rest des Codes bleibt unverändert
        self.category_buttons = [
            ft.ElevatedButton("Aufmaß", on_click=self.on_category_click, data="Aufmaß", width=150),
            ft.ElevatedButton("Material", on_click=self.on_category_click, data="Material", width=150),
            ft.ElevatedButton("Lohn", on_click=self.on_category_click, data="Lohn", width=150),
            ft.ElevatedButton("Festpreis", on_click=self.on_category_click, data="Festpreis", width=150)
        ]
        self.category_row = ft.Row(controls=self.category_buttons, spacing=10)

        # Restlicher Code bleibt unverändert
        self.dn_dropdown = ft.Dropdown(label="DN", on_change=self.update_dn_fields, width=80, options=[])
        self.da_dropdown = ft.Dropdown(label="DA", on_change=self.update_da_fields, width=80, options=[])
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=lambda e: update_price(self, e), width=120)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=lambda e: update_price(self, e), width=300)
        
        # Textfelder
        self.position_field = ft.TextField(label="Position", read_only=True, width=100)
        self.price_field = ft.TextField(label="Preis", read_only=True, width=100)
        self.quantity_input = ft.TextField(label="Menge", value="1", on_change=lambda e: update_price(self, e), width=90)
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True, width=160)
        self.total_price_field = ft.Text(
            value="Gesamtpreis: 0,00 €",
            style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD),
            text_align=ft.TextAlign.RIGHT
        )

        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege, width=180)
        
        self.zuschlaege_container = ft.Column(visible=False, spacing=10)

        # Sonderleistungen Button und Container
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen, width=200)
        self.sonderleistungen_container = ft.Container(
            content=ft.Column(controls=[], spacing=10),
            visible=False
        )

        # Update Position Button
        self.update_position_button = ft.ElevatedButton("Position aktualisieren", on_click=self.update_article_row, visible=False)

        # Kopfdaten-Felder
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

        # Erstellen Sie die DatePicker
        self.bestelldatum_picker = ft.DatePicker(
            on_change=self.on_bestelldatum_change,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31)
        )
        self.ausfuehrungsbeginn_picker = ft.DatePicker(
            on_change=self.on_ausfuehrungsbeginn_change,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31)
        )
        self.ausfuehrungsende_picker = ft.DatePicker(
            on_change=self.on_ausfuehrungsende_change,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2030, 12, 31)
        )

        self.page.overlay.extend([
            self.bestelldatum_picker,
            self.ausfuehrungsbeginn_picker,
            self.ausfuehrungsende_picker
        ])
        self.page.update()

        # Fügen Sie Buttons hinzu, um die DatePicker zu öffnen
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

        self.article_list = ft.Column()

        # Neue Buttons und Textfeld
        self.delete_invoice_button = ft.IconButton(
            icon=ft.icons.DELETE,
            tooltip="Rechnung löschen",
            on_click=self.delete_invoice
        )
        self.create_pdf_with_prices_button = ft.ElevatedButton(
            "PDF mit Preisen erstellen",
            on_click=self.create_pdf_with_prices,
            disabled=True
        )
        self.create_pdf_without_prices_button = ft.ElevatedButton(
            "PDF ohne Preise erstellen",
            on_click=self.create_pdf_without_prices,
            disabled=True
        )
        self.back_to_main_menu_button = ft.ElevatedButton(
            "Zurück zum Hauptmenü",
            on_click=self.back_to_main_menu
        )
        self.bemerkung_field = ft.TextField(
            label="Bemerkung",
            multiline=True,
            min_lines=3,
            max_lines=5
        )

        # Ändern Sie die Reihenfolge der Elemente in der Artikelzeile
        self.article_input_row = ft.Row([
            self.position_field,
            self.bauteil_dropdown,
            self.dn_dropdown,
            self.da_dropdown,
            self.dammdicke_dropdown,
            self.taetigkeit_dropdown,
            self.sonderleistungen_button,  # Sonderleistungen-Button hier eingefügt
            self.einheit_field,
            self.price_field,
            self.quantity_input,
            self.zwischensumme_field,
            ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
            self.update_position_button,
        ], alignment=ft.MainAxisAlignment.START, spacing=5)

        # Ändern Sie die Spaltennamen für die Artikelliste
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
            expand=True,
            horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
            vertical_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
        )

        # Kopfdaten-Felder in einem 3x3-Raster
        invoice_header = ft.Column([
            ft.Row([
                ft.Column([self.invoice_detail_fields['client_name']], expand=1),
                ft.Column([self.invoice_detail_fields['bestell_nr']], expand=1),
                ft.Column([self.invoice_detail_fields['aufmass_nr']], expand=1),
            ]),
            ft.Row([
                ft.Column([self.invoice_detail_fields['baustelle']], expand=1),
                ft.Column([self.invoice_detail_fields['anlagenteil']], expand=1),
                ft.Column([self.invoice_detail_fields['auftrags_nr']], expand=1),
            ]),
            ft.Row([
                ft.Column([self.bestelldatum_button], expand=1),
                ft.Column([self.ausfuehrungsbeginn_button], expand=1),
                ft.Column([self.ausfuehrungsende_button], expand=1),
            ]),
        ])

        # Versteckte Felder für die Datumswerte
        self.invoice_detail_fields['bestelldatum'].visible = False
        self.invoice_detail_fields['ausfuehrungsbeginn'].visible = False
        self.invoice_detail_fields['ausfuehrungsende'].visible = False

        # Fügen Sie die versteckten Felder zum Layout hinzu
        invoice_header.controls.extend([
            self.invoice_detail_fields['bestelldatum'],
            self.invoice_detail_fields['ausfuehrungsbeginn'],
            self.invoice_detail_fields['ausfuehrungsende'],
        ])

        self.nettobetrag_field = ft.TextField(label="Nettobetrag", read_only=True)
        self.zuschlaege_field = ft.TextField(label="Zuschläge", read_only=True)
        self.gesamtbetrag_field = ft.TextField(label="Gesamtbetrag", read_only=True)

    def validate_number_field(self, e, field_name):
        value = e.control.value
        pattern = r'^[0-9-]*$'
        if not re.match(pattern, value):
            e.control.error_text = "Nur Zahlen und Bindestriche erlaubt"
            self.update()
        else:
            e.control.error_text = None
            self.update()

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        logging.info(f"Sonderleistungen Container sichtbar: {self.sonderleistungen_container.visible}")
        if self.sonderleistungen_container.visible:
            self.create_sonderleistungen_checkboxes()  # Aktualisieren Sie die Checkboxen
        self.sonderleistungen_container.update()
        self.page.update()

    def toggle_zuschlaege(self, row):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.page.update()

    def create_sonderleistungen_checkboxes(self):
        sonderleistungen = self.load_sonderleistungen_from_db()
        checkboxes = [ft.Checkbox(label=sl, value=False, on_change=self.on_sonderleistung_change) for sl in sonderleistungen]
        self.sonderleistungen_container.content = ft.Column(controls=checkboxes, spacing=10)
        logging.info(f"Sonderleistungen Checkboxen erstellt: {len(checkboxes)}")

    def update_selected_faktoren(self, e, bezeichnung, faktor, art):
        if art == "Sonderleistung":
            if e.control.value:
                self.selected_sonderleistungen.append((bezeichnung, float(faktor)))
            else:
                self.selected_sonderleistungen = [item for item in self.selected_sonderleistungen if item[0] != bezeichnung]
        elif art == "Zuschlag":
            if e.control.value:
                self.selected_zuschlaege.append((bezeichnung, float(faktor)))
            else:
                self.selected_zuschlaege = [item for item in self.selected_zuschlaege if item[0] != bezeichnung]
        self.update_price()

    def on_sonderleistung_change(self, e):
        checkbox = e.control
        sonderleistung = checkbox.label
        faktor = self.get_sonderleistung_faktor(sonderleistung)  # Diese Methode müssen wir noch implementieren
        if checkbox.value:
            self.selected_sonderleistungen.append((sonderleistung, faktor))
        else:
            self.selected_sonderleistungen = [item for item in self.selected_sonderleistungen if item[0] != sonderleistung]
        self.update_price()
        self.page.update()

    def clear_input_fields(self):
        felder_zum_zuruecksetzen = [
            self.position_field,
            self.bauteil_dropdown,
            self.dn_dropdown,
            self.da_dropdown,
            self.dammdicke_dropdown,
            self.taetigkeit_dropdown,
            self.einheit_field,
            self.price_field,
            self.zwischensumme_field,
        ]
        
        for feld in felder_zum_zuruecksetzen:
            if isinstance(feld, ft.Dropdown):
                feld.value = None
            else:
                feld.value = ""
        
        # Setze das Mengenfeld auf "1"
        self.quantity_input.value = "1"
        
        self.dn_dropdown.visible = False
        self.da_dropdown.visible = False
        
        # Zurücksetzen der Sonderleistungen
        for checkbox in self.sonderleistungen_container.content.controls:
            checkbox.value = False
        self.selected_sonderleistungen = []
        
        self.page.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ? LIMIT 1', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def is_rohrleitung(self, bauteil):
        return bauteil.lower() == "rohrleitung"

    def auto_fill_rohrleitung_or_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            # Hole alle DN-Werte
            cursor.execute('SELECT DISTINCT DN FROM price_list WHERE Bauteil = "Rohrleitung" ORDER BY DN')
            dn_options = [row[0] for row in cursor.fetchall()]
            self.dn_dropdown.options = [ft.dropdown.Option(str(int(dn))) for dn in dn_options]
            self.dn_dropdown.value = str(int(dn_options[0]))

            # Hole alle DA-Werte für Rohrleitungen, unabhängig von DN
            cursor.execute('SELECT DISTINCT DA FROM price_list WHERE Bauteil = "Rohrleitung" ORDER BY DA')
            da_options = [row[0] for row in cursor.fetchall()]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]
            
            # Wähle den ersten DA-Wert, der für den ausgewählten DN verfügbar ist
            cursor.execute('SELECT MIN(DA) FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ?', (dn_options[0],))
            first_valid_da = cursor.fetchone()[0]
            self.da_dropdown.value = str(first_valid_da)

            self.dn_dropdown.visible = True
            self.da_dropdown.visible = True

            # Aktualisiere die Dämmdicke-Optionen und wähle die erste aus
            self.update_dammdicke_options()
            if self.dammdicke_dropdown.options:
                self.dammdicke_dropdown.value = self.dammdicke_dropdown.options[0].key

            # Hole die erste Tätigkeit
            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung LIMIT 1')
            first_taetigkeit = cursor.fetchone()[0]
            self.taetigkeit_dropdown.value = first_taetigkeit

            # Aktualisiere den Preis
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
    def edit_article_row(self, row_index):
        if 0 <= row_index < len(self.article_list_header.rows):
            row = self.article_list_header.rows[row_index]
            self.position_field.value = row.cells[0].content.value
            self.bauteil_dropdown.value = row.cells[1].content.value
            self.dn_dropdown.value = row.cells[2].content.value
            self.da_dropdown.value = row.cells[3].content.value
            self.dammdicke_dropdown.value = row.cells[4].content.value
            self.einheit_field.value = row.cells[5].content.value
            self.taetigkeit_dropdown.value = row.cells[6].content.value
            
            # Setzen Sie die Sonderleistungen
            sonderleistungen = row.cells[7].content.value.split(", ")
            for checkbox in self.sonderleistungen_container.content.controls:
                checkbox.value = checkbox.label in sonderleistungen
            self.selected_sonderleistungen = [(sl, self.get_sonderleistung_faktor(sl)) for sl in sonderleistungen if sl]
            
            self.price_field.value = row.cells[8].content.value
            self.quantity_input.value = row.cells[9].content.value
            self.zwischensumme_field.value = row.cells[10].content.value

            self.edit_mode = True
            self.edit_row_index = row_index
            self.update_position_button.visible = True
            self.update()
            logging.info(f"Artikelzeile {row_index} zum Bearbeiten geladen")
        else:
            logging.warning(f"Ungültiger Zeilenindex beim Bearbeiten: {row_index}")

    def get_sonderleistung_faktor(self, sonderleistung):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Sonderleistung" AND Bezeichnung = ?', (sonderleistung,))
            result = cursor.fetchone()
            return float(result[0]) if result else 1.0
        finally:
            cursor.close()

    def load_data(self):
        load_faktoren(self, "Sonstige Zuschläge")
        load_faktoren(self, "Sonderleistung")
        self.load_zuschlaege()

    def load_invoice_options(self):
        for field in self.invoice_detail_fields:
            options = self.get_from_cache_or_db(f"invoice_options_{field}", f"SELECT DISTINCT {field} FROM invoice WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
            self.invoice_detail_fields[field].options = [ft.dropdown.Option(str(option[0])) for option in options]
            self.invoice_detail_fields[field].options.append(ft.dropdown.Option("Neuer Eintrag"))

    def get_category_options(self):
        return [ft.dropdown.Option(cat) for cat in ["Aufmaß", "Material", "Lohn", "Festpreis"]]

    def on_category_click(self, e):
        # Setze alle Buttons zurück
        for button in self.category_buttons:
            button.style = None

        # Hebe den geklickten Button hervor
        e.control.style = ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE)

        # Aktualisiere die aktuelle Kategorie
        self.current_category = e.control.data

        # Führe die load_items Funktion aus
        load_items(self, self.current_category)

        self.update_field_visibility()
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
                    continue  # Wenn das neue Eingabefeld sichtbar und ausgefüllt ist, ist es okay
                return False, f"Bitte füllen Sie das Feld '{self.invoice_detail_fields[field].label}' aus."
        
        return True, ""

    def create_pdf_with_prices(self, e):
        logging.info("Starte PDF-Erstellung mit Preisen")
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

            filename = f"Rechnung_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(os.path.expanduser("~"), "Downloads", filename)
            logging.info(f"Versuche PDF zu erstellen: {filepath}")
            
            if not os.path.exists(os.path.dirname(filepath)):
                logging.warning(f"Zielordner existiert nicht: {os.path.dirname(filepath)}")
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                logging.info(f"Zielordner erstellt: {os.path.dirname(filepath)}")

            generate_pdf(invoice_data, filepath, include_prices=True)
            
            if os.path.exists(filepath):
                logging.info(f"PDF erfolgreich erstellt: {filepath}")
                self.show_snack_bar(f"PDF mit Preisen wurde erstellt: {filepath}")
            else:
                raise FileNotFoundError(f"PDF-Datei wurde nicht erstellt: {filepath}")

        except Exception as ex:
            logging.error(f"Fehler beim Erstellen des PDFs mit Preisen: {str(ex)}", exc_info=True)
            self.show_snack_bar(f"Fehler beim Erstellen des PDFs mit Preisen: {str(ex)}")

    def create_pdf_without_prices(self, e):
        logging.info("Starte PDF-Erstellung ohne Preise")
        is_valid, error_message = self.validate_invoice_details()
        if not is_valid:
            self.show_snack_bar(error_message)
            return

        try:
            invoice_data = self.get_invoice_data()
            logging.info(f"Rechnungsdaten erhalten: {invoice_data}")
            filename = f"Auftragsbestätigung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(os.path.expanduser("~"), "Downloads", filename)
            logging.info(f"Versuche PDF zu erstellen: {filepath}")
            generate_pdf(invoice_data, filepath, include_prices=False)
            logging.info("PDF erfolgreich erstellt")
            self.show_snack_bar(f"PDF ohne Preise wurde erstellt: {filepath}")
        except Exception as ex:
            logging.error(f"Fehler beim Erstellen des PDFs ohne Preise: {str(ex)}", exc_info=True)
            self.show_snack_bar(f"Fehler beim Erstellen des PDFs ohne Preise: {str(ex)}")

    def save_invoice_to_db(self, invoice_data):
        logging.info("Speichere Rechnung in der Datenbank")
        logging.debug(f"Rechnungsdaten: {invoice_data}")
        
        # Berechnen Sie den Nettobetrag
        nettobetrag = sum(float(article['zwischensumme']) for article in invoice_data['articles'])
        
        # Berechnen Sie die Zuschläge
        zuschlaege_summe = 0
        for zuschlag, faktor in invoice_data['zuschlaege']:
            zuschlag_betrag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag_betrag
        
        # Berechnen Sie den Gesamtbetrag
        total_price = nettobetrag + zuschlaege_summe
        
        logging.debug(f"Nettobetrag: {nettobetrag}")
        logging.debug(f"Zuschläge: {zuschlaege_summe}")
        logging.debug(f"Gesamtbetrag: {total_price}")
        
        cursor = self.conn.cursor()
        try:
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
                invoice_data['aufmass_nr'],
                invoice_data['auftrags_nr'],
                invoice_data['ausfuehrungsbeginn'],
                invoice_data['ausfuehrungsende'],
                total_price,
                ','.join([f"{z[0]}:{z[1]}" for z in invoice_data['zuschlaege']]),
                invoice_data.get('bemerkungen', '')
            ))
            invoice_id = cursor.lastrowid
            
            # Überprüfen Sie den gespeicherten Wert
            cursor.execute("SELECT total_amount FROM invoice WHERE id = ?", (invoice_id,))
            stored_total = cursor.fetchone()[0]
            logging.debug(f"Gespeicherter Gesamtpreis: {stored_total}")
            
            if abs(stored_total - total_price) > 0.01:  # Toleranz für Rundungsfehler
                logging.error(f"Gespeicherter Gesamtpreis ({stored_total}) weicht vom berechneten Preis ({total_price}) ab!")
            
            # Speichern der Artikel
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

    def save_invoice_to_db(self, invoice_data):
        logging.info("Speichere Rechnung in der Datenbank")
        logging.debug(f"Rechnungsdaten: {invoice_data}")
        
        # Berechnen Sie den Nettobetrag
        nettobetrag = sum(float(article['zwischensumme']) for article in invoice_data['articles'])
        
        # Berechnen Sie die Zuschläge
        zuschlaege_summe = 0
        for zuschlag, faktor in invoice_data['zuschlaege']:
            zuschlag_betrag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag_betrag
        
        # Berechnen Sie den Gesamtbetrag
        total_price = nettobetrag + zuschlaege_summe
        
        logging.debug(f"Nettobetrag: {nettobetrag}")
        logging.debug(f"Zuschläge: {zuschlaege_summe}")
        logging.debug(f"Gesamtbetrag: {total_price}")
        
        cursor = self.conn.cursor()
        try:
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
                self.next_aufmass_nr,  # Use the pre-calculated Aufmaß-Nr.
                invoice_data['auftrags_nr'],
                invoice_data['ausfuehrungsbeginn'],
                invoice_data['ausfuehrungsende'],
                total_price,
                ','.join([f"{z[0]}:{z[1]}" for z in invoice_data['zuschlaege']]),
                invoice_data.get('bemerkungen', '')
            ))
            invoice_id = cursor.lastrowid
            
            # Update the next_aufmass_nr for the next invoice
            self.next_aufmass_nr = str(int(self.next_aufmass_nr) + 1)
            self.invoice_detail_fields['aufmass_nr'].value = self.next_aufmass_nr
            
            # Überprüfen Sie den gespeicherten Wert
            cursor.execute("SELECT total_amount FROM invoice WHERE id = ?", (invoice_id,))
            stored_total = cursor.fetchone()[0]
            logging.debug(f"Gespeicherter Gesamtpreis: {stored_total}")
            
            if abs(stored_total - total_price) > 0.01:  # Toleranz für Rundungsfehler
                logging.error(f"Gespeicherter Gesamtpreis ({stored_total}) weicht vom berechneten Preis ({total_price}) ab!")
            
            # Speichern der Artikel
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

    def create_pdf_without_prices(self, e):
        logging.info("Starte PDF-Erstellung ohne Preise")
        is_valid, error_message = self.validate_invoice_details()
        if not is_valid:
            self.show_snack_bar(error_message)
            return

        try:
            invoice_data = self.get_invoice_data()
            invoice_data['bemerkungen'] = self.bemerkung_field.value
            logging.info(f"Rechnungsdaten erhalten: {invoice_data}")
            
            filename = f"Auftragsbestätigung_{self.next_aufmass_nr}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(os.path.expanduser("~"), "Downloads", filename)
            logging.info(f"Versuche PDF zu erstellen: {filepath}")
            
            if not os.path.exists(os.path.dirname(filepath)):
                logging.warning(f"Zielordner existiert nicht: {os.path.dirname(filepath)}")
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                logging.info(f"Zielordner erstellt: {os.path.dirname(filepath)}")

            generate_pdf(invoice_data, filepath, include_prices=False)
            
            if os.path.exists(filepath):
                logging.info(f"PDF erfolgreich erstellt: {filepath}")
                self.show_snack_bar(f"PDF ohne Preise wurde erstellt: {filepath}")
            else:
                raise FileNotFoundError(f"PDF-Datei wurde nicht erstellt: {filepath}")

        except Exception as ex:
            logging.error(f"Fehler beim Erstellen des PDFs ohne Preise: {str(ex)}", exc_info=True)
            self.show_snack_bar(f"Fehler beim Erstellen des PDFs ohne Preise: {str(ex)}")

    def load_zuschlaege(self):
        zuschlaege = self.get_from_cache_or_db("zuschlaege", 'SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', ("Zuschläge",))
        self.zuschlaege_container.controls.clear()
        for bezeichnung, faktor in zuschlaege:
            checkbox = ft.Checkbox(label=f"{bezeichnung}", value=False)
            checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_zuschlaege(e, b, f)
            self.zuschlaege_container.controls.append(checkbox)
        self.update()

    def update_selected_zuschlaege(self, e, bezeichnung, faktor):
        if e.control.value:
            self.selected_zuschlaege.append((bezeichnung, faktor))
        else:
            self.selected_zuschlaege = [item for item in self.selected_zuschlaege if item[0] != bezeichnung]
        self.update_total_price()
        self.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.update_total_price()  # Fügen Sie diese Zeile hinzu
        self.page.update()

    def reset_checkboxes(self):
        for checkbox in self.sonderleistungen_container.controls:
            if isinstance(checkbox, ft.Checkbox):
                checkbox.value = False
        self.selected_sonderleistungen.clear()
        self.update()

        # Nach dem Hinzufügen der Zeile, setzen Sie die Sonderleistungen zurück
        self.reset_checkboxes()
    
    def update_article_row(self, e):
        if self.edit_mode and self.edit_row_index is not None:
            if 0 <= self.edit_row_index < len(self.article_list_header.rows):
                sonderleistungen = ", ".join([sl[0] for sl in self.selected_sonderleistungen])
                updated_row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(self.position_field.value)),
                        ft.DataCell(ft.Text(self.bauteil_dropdown.value)),
                        ft.DataCell(ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "")),
                        ft.DataCell(ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "")),
                        ft.DataCell(ft.Text(self.dammdicke_dropdown.value)),
                        ft.DataCell(ft.Text(self.einheit_field.value)),
                        ft.DataCell(ft.Text(self.taetigkeit_dropdown.value)),
                        ft.DataCell(ft.Text(sonderleistungen)),
                        ft.DataCell(ft.Text(self.price_field.value)),
                        ft.DataCell(ft.Text(self.quantity_input.value)),
                        ft.DataCell(ft.Text(self.zwischensumme_field.value)),
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
                            ])
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

    def delete_invoice(self, e):
        # Implementieren Sie hier die Logik zum Löschen der Rechnung
        logging.info("Löschen der Rechnung wurde angefordert")
        # Beispiel für eine einfache Implementierung:
        if self.article_list_header.rows:
            self.article_list_header.rows.clear()
            self.article_summaries.clear()
            self.update_total_price()
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung wurde gelöscht"))
            self.page.snack_bar.open = True
        else:
            self.page.snack_bar = ft.SnackBar(content=ft.Text("Keine Rechnung zum Löschen vorhanden"))
            self.page.snack_bar.open = True
        self.update()
    def add_article_row(self, e):
        # Überprüfen Sie, ob die wichtigsten Felder ausgefüllt sind
        if not self.bauteil_dropdown.value:
            self.show_error("Bitte wählen Sie ein Bauteil aus.")
            return
        
        if not self.quantity_input.value or float(self.quantity_input.value) <= 0:
            self.show_error("Bitte geben Sie eine gültige Menge ein.")
            return
        
        if not self.price_field.value or float(self.price_field.value.replace(',', '.')) <= 0:
            self.show_error("Bitte geben Sie einen gültigen Preis ein.")
            return
        
        if not self.zwischensumme_field.value or float(self.zwischensumme_field.value.replace(',', '.')) <= 0:
            self.show_error("Bitte berechnen Sie die Zwischensumme.")
            return

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

        # Prüfe, ob ein identisches Produkt bereits existiert
        for row in self.article_list_header.rows:
            if (row.cells[0].content.value == position and
                row.cells[1].content.value == bauteil and
                row.cells[2].content.value == dn and
                row.cells[3].content.value == da and
                row.cells[4].content.value == dammdicke and
                row.cells[6].content.value == taetigkeit and
                row.cells[8].content.value == preis):
                
                self.show_error("Dieses Produkt wurde bereits hinzugefügt. Bitte ändern Sie die Menge oder fügen Sie Sonderleistungen hinzu, um es erneut hinzuzufügen.")
                return

        # Wenn kein identisches Produkt gefunden wurde, füge die neue Zeile hinzu
        new_row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(position)),
                ft.DataCell(ft.Text(bauteil)),
                ft.DataCell(ft.Text(dn)),
                ft.DataCell(ft.Text(da)),
                ft.DataCell(ft.Text(dammdicke)),
                ft.DataCell(ft.Text(einheit)),
                ft.DataCell(ft.Text(taetigkeit)),
                ft.DataCell(ft.Text(sonderleistungen)),
                ft.DataCell(ft.Text(preis)),
                ft.DataCell(ft.Text(menge)),
                ft.DataCell(ft.Text(zwischensumme)),
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
                    ])
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
        self.clear_input_fields()  # Dies setzt nun auch die Sonderleistungen zurück
        self.update_pdf_buttons()
        self.page.update()
        logging.info(f"Neue Artikelzeile hinzugefügt: {position}")

    def check_consistency(self):
        if len(self.article_list_header.rows) != len(self.article_summaries):
            logging.error(f"Inkonsistenz entdeckt: {len(self.article_list_header.rows)} Zeilen, aber {len(self.article_summaries)} Zusammenfassungen")
            # Hier könnten Sie auch Korrekturmaßnahmen implementieren

    def reset_sonderleistungen(self):
        for checkbox in self.sonderleistungen_container.content.controls:
            if isinstance(checkbox, ft.Checkbox):
                checkbox.value = False
        self.selected_sonderleistungen.clear()
        self.update()

    def update_field_visibility(self):
        logging.info(f"Updating field visibility for category: {self.current_category}")
        is_aufmass = self.current_category == "Aufmaß"
        
        self.dn_dropdown.visible = self.da_dropdown.visible = is_aufmass
        self.dammdicke_dropdown.visible = is_aufmass
        self.taetigkeit_dropdown.visible = is_aufmass
        
        self.bauteil_dropdown.visible = True
        self.quantity_input.visible = True
        self.price_field.visible = True
        self.zwischensumme_field.visible = True
        
        self.update()

    def update_total_price(self):
        logging.info("Starte Aktualisierung des Gesamtpreises")
        try:
            nettobetrag = sum(
                float(row.cells[10].content.value.replace(',', '.').replace('€', '').strip() or '0')
                for row in self.article_list_header.rows
            )
            logging.info(f"Berechneter Nettobetrag: {nettobetrag}")

            # Berechnung der Zuschläge
            zuschlaege_summe = 0
            for bezeichnung, faktor in self.selected_zuschlaege:
                zuschlag = nettobetrag * (float(faktor) - 1)
                zuschlaege_summe += zuschlag
                logging.info(f"Zuschlag '{bezeichnung}': {zuschlag:.2f}")

            gesamtbetrag = nettobetrag + zuschlaege_summe
            logging.info(f"Gesamtbetrag nach Zuschlägen: {gesamtbetrag}")

            # Aktualisieren der Anzeige
            self.nettobetrag_field.value = f"{nettobetrag:.2f} €"
            self.zuschlaege_field.value = f"{zuschlaege_summe:.2f} €"  # Neue Zeile
            self.gesamtbetrag_field.value = f"{gesamtbetrag:.2f} €"
            self.update()
        except Exception as e:
            logging.error(f"Fehler bei der Aktualisierung des Gesamtpreises: {str(e)}")
            logging.exception(e)

    def reset_fields(self):
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
        self.selected_zuschlaege = []
        self.update()

    def get_invoice_data(self):
        logging.info("Sammle Rechnungsdaten")
        invoice_data = {
            'client_name': self.invoice_detail_fields['client_name'].value if self.invoice_detail_fields['client_name'].value != "Neuer Eintrag" else self.new_entry_fields['client_name'].value,
            'bestell_nr': self.invoice_detail_fields['bestell_nr'].value if self.invoice_detail_fields['bestell_nr'].value != "Neuer Eintrag" else self.new_entry_fields['bestell_nr'].value,
            'bestelldatum': self.invoice_detail_fields['bestelldatum'].value if self.invoice_detail_fields['bestelldatum'].value != "Neuer Eintrag" else self.new_entry_fields['bestelldatum'].value,
            'baustelle': self.invoice_detail_fields['baustelle'].value if self.invoice_detail_fields['baustelle'].value != "Neuer Eintrag" else self.new_entry_fields['baustelle'].value,
            'anlagenteil': self.invoice_detail_fields['anlagenteil'].value if self.invoice_detail_fields['anlagenteil'].value != "Neuer Eintrag" else self.new_entry_fields['anlagenteil'].value,
            'aufmass_nr': self.next_aufmass_nr,  # Use the pre-calculated Aufmaß-Nr.
            'auftrags_nr': self.invoice_detail_fields['auftrags_nr'].value if self.invoice_detail_fields['auftrags_nr'].value != "Neuer Eintrag" else self.new_entry_fields['auftrags_nr'].value,
            'ausfuehrungsbeginn': self.invoice_detail_fields['ausfuehrungsbeginn'].value if self.invoice_detail_fields['ausfuehrungsbeginn'].value != "Neuer Eintrag" else self.new_entry_fields['ausfuehrungsbeginn'].value,
            'ausfuehrungsende': self.invoice_detail_fields['ausfuehrungsende'].value if self.invoice_detail_fields['ausfuehrungsende'].value != "Neuer Eintrag" else self.new_entry_fields['ausfuehrungsende'].value,
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

        # Berechnen Sie den Gesamtpreis mit Zuschlägen
        total_price = invoice_data['net_total']
        for _, faktor in invoice_data['zuschlaege']:
            total_price *= float(faktor)

        invoice_data['total_price'] = total_price

        logging.info(f"Gesammelte Rechnungsdaten: {invoice_data}")
        return invoice_data

    def get_taetigkeit_id(self, taetigkeit_name):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT id FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit_name,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def on_client_change(self, e):
        if e.control.value == "Neuer Eintrag":
            self.new_entry_fields['client_name'].visible = True
        else:
            self.new_entry_fields['client_name'].visible = False
            # Hier können Sie Logik hinzufügen, um andere Felder basierend auf dem ausgewählten Kunden zu aktualisieren
        self.update()

    def on_order_change(self, e):
        if e.control.value == "Neuer Eintrag":
            self.new_entry_fields['bestell_nr'].visible = True
        else:
            self.new_entry_fields['bestell_nr'].visible = False
            # Hier können Sie Logik hinzufügen, um andere Felder basierend auf der ausgewählten Bestellnummer zu aktualisieren
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

    def update_dn_fields(self, e):
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            cursor = self.conn.cursor()
            try:
                # Finde den ersten gültigen DA-Wert für den ausgewählten DN
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
                # Finde den ersten gültigen DN-Wert für den ausgewählten DA
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

    def update_dammdicke_options(self, e=None):
        bauteil = self.bauteil_dropdown.value
        if not bauteil:
            return

        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None

        dammdicke_options = get_dammdicke_options(self, bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        if dammdicke_options:
            self.dammdicke_dropdown.value = str(dammdicke_options[0])  # Wählt die kleinste Dämmdicke als Standard
        else:
            self.dammdicke_dropdown.value = None
        self.dammdicke_dropdown.update()

    def show_error(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.colors.RED_400)
        self.page.snack_bar.open = True
        self.update()

    def toggle_new_entry(self, e, field):
        dropdown = self.invoice_detail_fields[field]
        text_field = self.new_entry_fields[field]
        text_field.visible = dropdown.value == "Neuer Eintrag"
        self.update()

    def remove_article_row(self, row):
        logging.info(f"Versuche, Zeile zu entfernen: {row}")
        logging.info(f"Anzahl der Zeilen vor dem Entfernen: {len(self.article_list_header.rows)}")
        logging.info(f"Anzahl der Zusammenfassungen vor dem Entfernen: {len(self.article_summaries)}")
        
        if row in self.article_list_header.rows:
            index = self.article_list_header.rows.index(row)
            logging.info(f"Gefundener Index der zu entfernenden Zeile: {index}")
            
            self.article_list_header.rows.remove(row)
            logging.info(f"Zeile aus article_list_header entfernt. Neue Anzahl: {len(self.article_list_header.rows)}")
            
            if 0 <= index < len(self.article_summaries):
                del self.article_summaries[index]
                logging.info(f"Zusammenfassung entfernt. Neue Anzahl: {len(self.article_summaries)}")
            else:
                logging.warning(f"Index {index} außerhalb des Bereichs von article_summaries")
            
            self.update_total_price()
            self.update_pdf_buttons()  # Neue Methode aufrufen
            self.update()
            logging.info("Zeile erfolgreich entfernt und UI aktualisiert")
        else:
            logging.warning("Versuchte Zeile zu entfernen, die nicht in der Tabelle existiert")
        
        logging.info(f"Anzahl der Zeilen nach dem Entfernen: {len(self.article_list_header.rows)}")
        logging.info(f"Anzahl der Zusammenfassungen nach dem Entfernen: {len(self.article_summaries)}")

    def update_pdf_buttons(self):
        has_articles = len(self.article_list_header.rows) > 0
        logging.info(f"Updating PDF buttons. Has articles: {has_articles}")
        self.create_pdf_with_prices_button.disabled = not has_articles
        self.create_pdf_without_prices_button.disabled = not has_articles
        self.update()

    def load_faktoren(self, art):
        faktoren = self.get_from_cache_or_db(f"faktoren_{art}", 'SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        container = self.sonderleistungen_container.content if art == "Sonderleistung" else self.zuschlaege_container
        container.controls.clear()
        for bezeichnung, faktor in faktoren:
            checkbox = ft.Checkbox(label=f"{bezeichnung}", value=False)
            checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_faktoren_and_price(e, b, f, art)
            container.controls.append(checkbox)
        self.update()

    def update_selected_faktoren_and_price(self, e, bezeichnung, faktor, art):
        self.update_selected_faktoren(e, bezeichnung, faktor, art)
        self.update_price()
        self.update_total_price()  # Aktualisiere den Gesamtpreis
        self.update()  # Aktualisiere die Benutzeroberfläche

    def update_price(self, e=None):
        logging.info("Starte Preisberechnung")
        category = self.current_category
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        quantity = self.quantity_input.value

        logging.info(f"Kategorie: {category}, Bauteil: {bauteil}, DN: {dn}, DA: {da}, Dämmdicke: {dammdicke}, Tätigkeit: {taetigkeit}, Menge: {quantity}")

        if not all([category, bauteil, quantity]):
            logging.warning("Nicht alle erforderlichen Felder sind ausgefüllt")
            self.price_field.value = ""
            self.zwischensumme_field.value = ""
            return

        try:
            quantity = float(quantity)
        except ValueError:
            logging.error(f"Ungültige Menge: {quantity}")
            self.show_error("Ungültige Menge")
            self.price_field.value = ""
            self.zwischensumme_field.value = ""
            return

        if category == "Aufmaß":
            if not all([taetigkeit, dammdicke]):
                logging.warning("Tätigkeit oder Dämmdicke fehlt für Aufmaß")
                return

            base_price = get_base_price(self, bauteil, dn, da, dammdicke)
            logging.info(f"Basispreis: {base_price}")
            if base_price is None:
                logging.error("Kein Preis gefunden")
                self.show_error("Kein Preis gefunden")
                return

            taetigkeit_faktor = get_taetigkeit_faktor(self, taetigkeit)
            logging.info(f"Tätigkeitsfaktor: {taetigkeit_faktor}")
            if taetigkeit_faktor is None:
                logging.error("Kein Tätigkeitsfaktor gefunden")
                self.show_error("Kein Tätigkeitsfaktor gefunden")
                return

            price = base_price * taetigkeit_faktor

        elif category == "Material":
            price = get_material_price(self, bauteil)
            logging.info(f"Materialpreis: {price}")
            if price is None:
                logging.error("Kein Materialpreis gefunden")
                self.show_error("Kein Materialpreis gefunden")
                return

        else:
            logging.error(f"Preisberechnung für Kategorie {category} nicht implementiert")
            self.show_error("Preisberechnung für diese Kategorie nicht implementiert")
            return

        # Sonderleistungen hinzufügen
        sonderleistungen_aufschlag = 0
        for sonderleistung, faktor in self.selected_sonderleistungen:
            aufschlag = price * (float(faktor) - 1)
            sonderleistungen_aufschlag += aufschlag
            logging.info(f"Sonderleistung '{sonderleistung}' angewendet, Aufschlag: {aufschlag:.2f}")

        price_with_sonderleistungen = price + sonderleistungen_aufschlag
        total_price = price_with_sonderleistungen * quantity

        logging.info(f"Basispreis: {price:.2f}, Mit Sonderleistungen: {price_with_sonderleistungen:.2f}, Gesamtpreis: {total_price:.2f}")

        self.price_field.value = f"{price_with_sonderleistungen:.2f}"
        self.zwischensumme_field.value = f"{total_price:.2f}"
        
        self.update()

    def delete_article_row(self, row_index):
        if 0 <= row_index < len(self.article_list_header.rows):
            del self.article_list_header.rows[row_index]
            del self.article_summaries[row_index]
            
            # Aktualisiere self.edit_row_index, wenn nötig
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

    def check_existing_invoice(self):
        cursor = self.conn.cursor()
        try:
            # Hier nehmen wir an, dass Sie einen eindeutigen Identifier für die Rechnung haben,
        # z.B. eine Kombination aus Kundennummer und Datum
            cursor.execute("""  
                SELECT AufmassNr FROM Aufmass 
                WHERE KundenNr = ? AND Datum = ?
            """, (self.kunden_nr_field.value, self.datum_field.value))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def generate_pdf(self, include_prices=True):
        if not self.article_list_header.rows:
            self.show_error("Keine Artikel hinzugefügt. Bitte fügen Sie mindestens einen Artikel hinzu.")
            return

        existing_aufmass_nr = self.check_existing_invoice()
        
        if existing_aufmass_nr:
            self.current_aufmass_nr = existing_aufmass_nr
            invoice_data = self.load_invoice_data(existing_aufmass_nr)
        else:
            if not hasattr(self, 'current_aufmass_nr'):
                self.current_aufmass_nr = self.get_next_aufmass_nr()
        invoice_data = self.prepare_invoice_data()
        self.save_invoice_data(invoice_data)

        invoice_data['aufmass_nr'] = self.current_aufmass_nr

        # Fügen Sie hier die zusätzlichen Felder hinzu, die in der PDF-Generierung verwendet werden
        invoice_data.update({
        'client_name': self.kunde_field.value,
        'bestell_nr': self.bestellnr_field.value,
        'bestelldatum': self.bestelldatum_field.value,
        'baustelle': self.baustelle_field.value,
        'anlagenteil': self.anlagenteil_field.value,
        'auftrags_nr': self.auftragsnr_field.value,
        'ausfuehrungsbeginn': self.ausfuehrungsbeginn_field.value,
        'ausfuehrungsende': self.ausfuehrungsende_field.value,
        'bemerkung': self.bemerkung_field.value,
        'zuschlaege': self.selected_zuschlaege,
        'net_total': self.calculate_net_total(),
        'articles': self.prepare_articles_data()
        })

        file_name = f"Aufmass_{self.current_aufmass_nr}{'_mit_preisen' if include_prices else ''}.pdf"
        output_path = os.path.join(os.path.expanduser("~"), "Desktop", file_name)

        from .invoice_pdf_generator import generate_pdf as pdf_generator
        pdf_generator(invoice_data, output_path, include_prices)
        self.show_success(f"PDF wurde erstellt: {output_path}")

    def calculate_net_total(self):
        return sum(float(row.cells[10].content.value.replace(',', '.').replace('€', '').strip() or '0')
                for row in self.article_list_header.rows)

    def prepare_articles_data(self):
        return [
            {
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
            for row in self.article_list_header.rows
        ]           

    def apply_zuschlaege(self, nettobetrag):
        zuschlaege_summe = 0
        for bezeichnung, faktor in self.selected_zuschlaege:
            zuschlag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag
            logging.info(f"Zuschlag '{bezeichnung}': {zuschlag:.2f}")
        
        gesamtbetrag = nettobetrag + zuschlaege_summe
        return gesamtbetrag

    def back_to_main_menu(self, e):
        self.page.go('/')  # Angenommen, '/' ist die Route für das Hauptmenü