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
        logging.info("Initializing InvoiceForm")
        self.page = page
        self.conn = get_db_connection()
        self.main_page = page  # Speichern Sie die Hauptseite für die Rückkehr zum Hauptmenü
        
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
        
        logging.info("Creating UI elements")
        self.new_entry_fields = {}
        self.create_ui_elements()
        self.load_invoice_options()
        logging.info("Loading data")
        self.load_data()
        load_items(self, self.current_category)  # Laden Sie die Items basierend auf der Standardkategorie
        self.update_price()  # Initialisieren Sie die Preisberechnung
        logging.info("InvoiceForm initialization complete")

    def create_ui_elements(self):
        # ... andere UI-Elemente ...

        self.invoice_detail_fields = {
            'client_name': ft.Dropdown(label="Kunde"),
            'bestell_nr': ft.Dropdown(label="Bestellnummer"),
            'bestelldatum': ft.TextField(label="Bestelldatum", read_only=True),
            'baustelle': ft.TextField(label="Baustelle"),
            'anlagenteil': ft.TextField(label="Anlagenteil"),
            'aufmass_nr': ft.TextField(label="Aufmaß-Nr."),
            'auftrags_nr': ft.TextField(label="Auftrags-Nr."),
            'ausfuehrungsbeginn': ft.TextField(label="Ausführungsbeginn", read_only=True),
            'ausfuehrungsende': ft.TextField(label="Ausführungsende", read_only=True)
        }

        self.new_entry_fields = {
            key: ft.TextField(label=f"Neuer {value.label}", visible=False)
            for key, value in self.invoice_detail_fields.items()
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

        # ... Rest der Methode bleibt unverändert ...

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
        # Kopfdaten-Layout in 3x3 Feldern
        invoice_details = ft.Column([
            ft.Row([
                ft.Column([self.invoice_detail_fields['client_name'], self.new_entry_fields['client_name']]),
                ft.Column([self.invoice_detail_fields['bestell_nr'], self.new_entry_fields['bestell_nr']]),
                ft.Column([self.invoice_detail_fields['bestelldatum'], self.bestelldatum_button])
            ]),
            ft.Row([
                ft.Column([self.invoice_detail_fields['baustelle'], self.new_entry_fields['baustelle']]),
                ft.Column([self.invoice_detail_fields['anlagenteil'], self.new_entry_fields['anlagenteil']]),
                ft.Column([self.invoice_detail_fields['aufmass_nr'], self.new_entry_fields['aufmass_nr']])
            ]),
            ft.Row([
                ft.Column([self.invoice_detail_fields['auftrags_nr'], self.new_entry_fields['auftrags_nr']]),
                ft.Column([self.invoice_detail_fields['ausfuehrungsbeginn'], self.ausfuehrungsbeginn_button]),
                ft.Column([self.invoice_detail_fields['ausfuehrungsende'], self.ausfuehrungsende_button])
            ]),
        ])
        # Logo hinzufügen
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                             'assets', 'logos', 'KAE_Logo_RGB_300dpi2.jpg')
        logo = ft.Image(src=logo_path, width=100, height=50)  # Logo-Pfad aus der Konstante
        logo_container = ft.Container(content=logo)

        self.nettobetrag_field = ft.TextField(label="Nettobetrag", read_only=True)
        self.zuschlaege_field = ft.TextField(label="Zuschläge", read_only=True)
        self.gesamtbetrag_field = ft.TextField(label="Gesamtbetrag", read_only=True)
        
        total_price_row = ft.Row([
            self.nettobetrag_field,
            self.zuschlaege_field,
            self.gesamtbetrag_field
        ])

        # Hauptlayout
        main_content = ft.Column([
            ft.Row([logo_container], alignment=ft.MainAxisAlignment.END),  # Logo in einer Zeile rechts ausrichten
            ft.Row([self.delete_invoice_button], alignment=ft.MainAxisAlignment.END),
            invoice_details,
            ft.Container(height=20),
            self.article_input_row_with_container,
            ft.Container(height=20),
            self.article_list_header,
            total_price_row,
            ft.Container(height=20),
            ft.Row([
                ft.Column([
                    self.bemerkung_field,
                ], expand=1),
                ft.Column([
                    self.zuschlaege_button,
                    self.zuschlaege_container,
                    ft.Container(height=10),
                    self.create_pdf_with_prices_button,
                    ft.Container(height=10),
                    self.create_pdf_without_prices_button,
                    ft.Container(height=10),
                    self.back_to_main_menu_button,
                ], expand=1),
            ]),
        ])

        # Wrap the main content in a ListView
        return ft.Container(
            content=ft.ListView(
                [main_content],
                expand=1,
                spacing=10,
                padding=20,
            ),
            padding=20,
            expand=True,
        )


    def show_snack_bar(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

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

        # Buttons und Container
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen, width=200)
        # Container für Sonderleistungen
        self.sonderleistungen_container = ft.Container(
            content=ft.Column(controls=[], spacing=10),
            visible=False
        )
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege, width=180)
        
        self.zuschlaege_container = ft.Column(visible=False, spacing=10)

        # Update Position Button
        self.update_position_button = ft.ElevatedButton("Position aktualisieren", on_click=self.update_article_row, visible=False)

        # Kopfdaten-Felder
        self.invoice_detail_fields = {
            'client_name': ft.Dropdown(label="Kunde", on_change=lambda e: self.toggle_new_entry(e, "client_name")),
            'bestell_nr': ft.Dropdown(label="Bestell-Nr.", on_change=lambda e: self.toggle_new_entry(e, "bestell_nr")),
            'bestelldatum': ft.TextField(label="Bestelldatum", read_only=True),
            'baustelle': ft.Dropdown(label="Baustelle", on_change=lambda e: self.toggle_new_entry(e, "baustelle")),
            'anlagenteil': ft.Dropdown(label="Anlagenteil", on_change=lambda e: self.toggle_new_entry(e, "anlagenteil")),
            'aufmass_nr': ft.Dropdown(label="Aufmaß-Nr.", on_change=lambda e: self.toggle_new_entry(e, "aufmass_nr")),
            'auftrags_nr': ft.Dropdown(label="Auftrags-Nr.", on_change=lambda e: self.toggle_new_entry(e, "auftrags_nr")),
            'ausfuehrungsbeginn': ft.TextField(label="Ausführungsbeginn", read_only=True),
            'ausfuehrungsende': ft.TextField(label="Ausführungsende", read_only=True)
        }
        self.new_entry_fields = {key: ft.TextField(label=f"Neuer {value.label}", visible=False) for key, value in self.invoice_detail_fields.items()}

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
            on_click=self.create_pdf_with_prices
        )
        self.create_pdf_without_prices_button = ft.ElevatedButton(
            "PDF ohne Preise erstellen",
            on_click=self.create_pdf_without_prices
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
            self.sonderleistungen_button,  # Button für Sonderleistungen
            self.sonderleistungen_container,  # Container für Sonderleistungen
            self.einheit_field,
            self.price_field,
            self.quantity_input,
            self.zwischensumme_field,
            ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
            self.update_position_button,
        ], alignment=ft.MainAxisAlignment.START, wrap=True)

        # Fügen Sie eine neue Zeile für den Container hinzu
        self.article_input_row_with_container = ft.Column([
            self.article_input_row,
            self.sonderleistungen_container  # Container für Sonderleistungen in der nächsten Zeile
        ])

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

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]


    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.update_total_price()  # Fügen Sie diese Zeile hinzu
        self.update()

    def toggle_sonderleistungen(self, row):
        # Hier können Sie die Logik implementieren, um die Optionen für Sonderleistungen anzuzeigen
        # Zum Beispiel:
        if self.sonderleistungen_container.visible:
            self.sonderleistungen_container.visible = False
        else:
            self.sonderleistungen_container.visible = True
            # Positionieren Sie den Container unter dem Button
            # Sie können die Positionierung anpassen, um sicherzustellen, dass es unter dem Button angezeigt wird
        self.update()

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

    def clear_input_fields(self):
        felder_zum_zuruecksetzen = [
            self.position_field,
            self.bauteil_dropdown,
            self.dn_dropdown,
            self.da_dropdown,
            self.dammdicke_dropdown,
            self.einheit_field,
            self.taetigkeit_dropdown,
            self.quantity_input,
            self.price_field,
            self.zwischensumme_field
        ]
        
        for feld in felder_zum_zuruecksetzen:
            feld.value = None if isinstance(feld, ft.Dropdown) else ""
        
        # Zurücksetzen der Sonderleistungen
        for checkbox in self.sonderleistungen_container.content.controls:
            if isinstance(checkbox, ft.Checkbox):
                checkbox.value = False
        
        self.selected_sonderleistungen = []
        
        self.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

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

    def edit_article_row(self, row):
        self.edit_mode = True
        self.edit_row_index = self.article_list_header.rows.index(row)
        
        self.position_field.value = row.cells[0].content.value
        self.bauteil_dropdown.value = row.cells[1].content.value
        self.dn_dropdown.value = row.cells[2].content.value
        self.da_dropdown.value = row.cells[3].content.value
        self.dammdicke_dropdown.value = row.cells[4].content.value
        self.einheit_field.value = row.cells[5].content.value
        self.taetigkeit_dropdown.value = row.cells[6].content.value
        self.price_field.value = row.cells[8].content.value
        self.quantity_input.value = row.cells[9].content.value
        self.zwischensumme_field.value = row.cells[10].content.value
        
        # Reset sonderleistungen
        for checkbox in self.sonderleistungen_container.content.controls:
            checkbox.value = False
        
        # Set selected sonderleistungen
        sonderleistungen = row.cells[7].content.value.split(", ")
        for checkbox in self.sonderleistungen_container.content.controls:
            if checkbox.label.split(' (')[0] in sonderleistungen:
                checkbox.value = True
        
        self.update_position_button.visible = True
        self.update()

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

    def create_pdf_with_prices(self, e):
        logging.info("Starte PDF-Erstellung mit Preisen")
        try:
            invoice_data = self.get_invoice_data()
            invoice_data['bemerkungen'] = self.bemerkung_field.value  # Fügen Sie die Bemerkungen hinzu
            logging.info(f"Rechnungsdaten erhalten: {invoice_data}")

            # Speichern der Rechnung in der Datenbank und Erhalten der invoice_id
            invoice_id = self.save_invoice_to_db(invoice_data)
            if invoice_id is None:
                raise Exception("Fehler beim Speichern der Rechnung in der Datenbank")

            filename = f"Rechnung_{invoice_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(os.path.expanduser("~"), "Downloads", filename)
            logging.info(f"Versuche PDF zu erstellen: {filepath}")
            
            # Überprüfen Sie, ob der Ordner existiert
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
            return None
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Speichern der Rechnung: {str(e)}")
            self.conn.rollback()
            return None
        finally:
            cursor.close()

    def create_pdf_without_prices(self, e):
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

    def load_zuschlaege(self):
        zuschlaege = self.get_from_cache_or_db("zuschlaege", 'SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', ("Zuschläge",))
        self.zuschlaege_container.controls.clear()
        for bezeichnung, faktor in zuschlaege:
            checkbox = ft.Checkbox(label=f"{bezeichnung}", value=False)
            checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_zuschlaege(e, b, f)
            self.zuschlaege_container.controls.append(checkbox)
        self.update()

    def update_total_price(self):
        logging.info("Starte Aktualisierung des Gesamtpreises")
        
        try:
            nettobetrag = sum(float(row.cells[10].content.value.replace(',', '.').replace('€', '').strip()) for row in self.article_list_header.rows)
            logging.info(f"Berechneter Nettobetrag: {nettobetrag:.2f}")
            
            zuschlaege_summe = 0
            for bezeichnung, faktor in self.selected_zuschlaege:
                zuschlag = nettobetrag * (float(faktor) - 1)
                zuschlaege_summe += zuschlag
                logging.info(f"Zuschlag '{bezeichnung}': {zuschlag:.2f}")

            gesamtbetrag = nettobetrag + zuschlaege_summe
            logging.info(f"Berechneter Gesamtbetrag: {gesamtbetrag:.2f}")

            self.nettobetrag_field.value = f"{nettobetrag:.2f} €"
            self.zuschlaege_field.value = f"{zuschlaege_summe:.2f} €"
            self.gesamtbetrag_field.value = f"{gesamtbetrag:.2f} €"

            self.nettobetrag_field.update()
            self.zuschlaege_field.update()
            self.gesamtbetrag_field.update()

            self.update()
            logging.info("Gesamtpreis-Aktualisierung abgeschlossen")
        except Exception as e:
            logging.error(f"Fehler bei der Aktualisierung des Gesamtpreises: {str(e)}", exc_info=True)

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
        self.update()

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
            if float(self.price_field.value or 0) == 0:
                self.show_error("Der Preis darf nicht Null sein.")
                return

            # Entfernen der Klammern bei den Sonderleistungen
            sonderleistungen_text = ", ".join([sl[0].split(' (')[0] for sl in self.selected_sonderleistungen])

            updated_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(self.position_field.value)),
                    ft.DataCell(ft.Text(self.bauteil_dropdown.value)),
                    ft.DataCell(ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "")),
                    ft.DataCell(ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "")),
                    ft.DataCell(ft.Text(self.dammdicke_dropdown.value)),
                    ft.DataCell(ft.Text(self.einheit_field.value)),
                    ft.DataCell(ft.Text(self.taetigkeit_dropdown.value)),
                    ft.DataCell(ft.Text(sonderleistungen_text)),
                    ft.DataCell(ft.Text(self.price_field.value)),
                    ft.DataCell(ft.Text(self.quantity_input.value)),
                    ft.DataCell(ft.Text(self.zwischensumme_field.value)),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT, on_click=lambda _: self.edit_article_row(updated_row)),
                        ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _: self.remove_article_row(updated_row))
                    ])),
                ]
            )
            
            self.article_list_header.rows[self.edit_row_index] = updated_row
            self.edit_mode = False
            self.edit_row_index = None
            self.update_position_button.visible = False
            self.clear_input_fields()
            self.update_total_price()
            self.update()
        else:
            self.show_error("Keine Zeile zum Aktualisieren ausgewählt.")

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
        logging.info("Füge neue Artikelzeile hinzu")
        
        # Einfache Validierung
        if not all([self.bauteil_dropdown.value, self.quantity_input.value, self.price_field.value]):
            self.show_error("Bitte füllen Sie alle erforderlichen Felder aus.")
            return

        position = self.position_field.value
        
        # Entfernen der Klammern bei den Sonderleistungen
        sonderleistungen_text = ", ".join([sl[0].split(' (')[0] for sl in self.selected_sonderleistungen])
        
        new_row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(position)),
                ft.DataCell(ft.Text(self.bauteil_dropdown.value)),
                ft.DataCell(ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "")),
                ft.DataCell(ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "")),
                ft.DataCell(ft.Text(self.dammdicke_dropdown.value)),
                ft.DataCell(ft.Text(self.einheit_field.value)),
                ft.DataCell(ft.Text(self.taetigkeit_dropdown.value)),
                ft.DataCell(ft.Text(sonderleistungen_text)),
                ft.DataCell(ft.Text(self.price_field.value)),
                ft.DataCell(ft.Text(self.quantity_input.value)),
                ft.DataCell(ft.Text(self.zwischensumme_field.value)),
                ft.DataCell(ft.Row([
                    ft.IconButton(icon=ft.icons.EDIT, on_click=lambda _: self.edit_article_row(new_row)),
                    ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _: self.remove_article_row(new_row))
                ])),
            ]
        )
        
        self.article_list_header.rows.append(new_row)
        
        summary_data = {
            'zwischensumme': float(self.zwischensumme_field.value.replace(',', '.')),
            'sonderleistungen': self.selected_sonderleistungen.copy()
        }
        self.article_summaries.append(summary_data)
        
        self.update_total_price()
        self.clear_input_fields()
        self.update()
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
            nettobetrag = sum(float(row.cells[10].content.value.replace(',', '.').replace('€', '').strip()) for row in self.article_list_header.rows)
            logging.info(f"Berechneter Nettobetrag: {nettobetrag:.2f}")
            
            # Anwenden der Zuschläge auf den Gesamtbetrag
            gesamtbetrag = self.apply_zuschlaege(nettobetrag)
            zuschlaege_summe = gesamtbetrag - nettobetrag
            logging.info(f"Zuschläge Summe: {zuschlaege_summe:.2f}")
            logging.info(f"Berechneter Gesamtbetrag: {gesamtbetrag:.2f}")

            self.nettobetrag_field.value = f"{nettobetrag:.2f} €"
            self.zuschlaege_field.value = f"{zuschlaege_summe:.2f} €"
            self.gesamtbetrag_field.value = f"{gesamtbetrag:.2f} €"

            self.nettobetrag_field.update()
            self.zuschlaege_field.update()
            self.gesamtbetrag_field.update()

            self.update()
            logging.info("Gesamtpreis-Aktualisierung abgeschlossen")
        except Exception as e:
            logging.error(f"Fehler bei der Aktualisierung des Gesamtpreises: {str(e)}", exc_info=True)

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
            'aufmass_nr': self.invoice_detail_fields['aufmass_nr'].value if self.invoice_detail_fields['aufmass_nr'].value != "Neuer Eintrag" else self.new_entry_fields['aufmass_nr'].value,
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
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
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
            self.update()
            logging.info("Zeile erfolgreich entfernt und UI aktualisiert")
        else:
            logging.warning("Versuchte Zeile zu entfernen, die nicht in der Tabelle existiert")
        
        logging.info(f"Anzahl der Zeilen nach dem Entfernen: {len(self.article_list_header.rows)}")
        logging.info(f"Anzahl der Zusammenfassungen nach dem Entfernen: {len(self.article_summaries)}")

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