import logging
import sqlite3
from tkinter import dialog
import flet as ft
import re
import os
from datetime import datetime

from database.db_operations import get_db_connection
from .invoice_pdf_generator import generate_pdf
from .invoice_form_helpers import (
    load_items, get_dammdicke_options, get_base_price,
    get_material_price, get_taetigkeit_faktor, update_price, get_positionsnummer
)

class InvoiceForm(ft.UserControl):
    def __init__(self, page, aufmass_nr=None, is_preview=False, initial_color_scheme="BLUE", initial_theme_mode=ft.ThemeMode.LIGHT):
        super().__init__()
        self.page = page
        self.next_aufmass_nr = self.get_next_aufmass_nr()
        self.cache = {}
        self.article_summaries = []
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        self.current_category = "Aufmaß"
        self.edit_mode = False
        self.topbar = None
        self.edit_row_index = None
        self.article_count = 0
        self.pdf_generated = False
        self.is_preview = is_preview
        self.color_scheme = initial_color_scheme
        self.theme_mode = initial_theme_mode

        # Erstellen Sie die UI-Elemente
        self.create_ui_elements()

        # Erstellen Sie die Buttons hier
        self.create_action_buttons()

        # Setzen Sie die Sichtbarkeit der Buttons
        self.save_invoice_with_pdf_button.visible = False
        self.save_invoice_without_pdf_button.visible = False
        self.new_aufmass_button.visible = False

        # Erstellen Sie die Dialoge
        self.create_dialogs()

        logging.info("Initializing InvoiceForm")
        self.load_invoice_options()
        if aufmass_nr:
            self.load_invoice_data(aufmass_nr)
        else:
            self.load_last_invoice_data()
        logging.info("Loading data")
        self.load_data()
        load_items(self, self.current_category)
        self.update_price()
        logging.info("InvoiceForm initialization complete")

        if self.is_preview:
            self.disable_all_inputs()

        self.initialize_ui()
        self.update_theme()  # Statt load_color_scheme() verwenden wir update_theme()
        self.update_summary_buttons()

        # Add the TopBar
        self.add_logo_and_topbar()

    def update_theme(self):
        """Aktualisiert das Farbschema und Theme der Formular-Elemente"""
        if hasattr(self.page, 'theme'):
            self.page.theme = ft.Theme(
                color_scheme=ft.ColorScheme(
                    primary=getattr(ft.colors, self.color_scheme),
                    on_primary=ft.colors.WHITE,
                )
            )
            self.page.bgcolor = ft.colors.WHITE if self.theme_mode == ft.ThemeMode.LIGHT else ft.colors.BLACK
            self.update()
            self.page.update()

    def change_color_scheme(self, color):
        """Ändert das Farbschema des Formulars"""
        self.color_scheme = color
        self.update_theme()

    def toggle_theme(self, e):
        """Wechselt zwischen hellem und dunklem Theme"""
        self.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self.update_theme()

    def create_dialogs(self):
        # Settings Dialog
        self.settings_dialog = ft.AlertDialog(
            title=ft.Text("Einstellungen"),
            content=ft.Column([
                ft.Dropdown(
                    label="Farbschema",
                    options=[
                        ft.dropdown.Option("BLUE"),
                        ft.dropdown.Option("RED"),
                        ft.dropdown.Option("GREEN"),
                        # Fügen Sie hier weitere Farboptionen hinzu
                    ],
                    on_change=self.change_color_scheme
                )
            ]),
            actions=[
                ft.TextButton("Schließen", on_click=self.close_settings_dialog)
            ],
        )

        # Help Dialog
        self.help_dialog = ft.AlertDialog(
            title=ft.Text("Hilfe"),
            content=ft.Text("""
            Hier können Sie eine Hilfe-Anleitung für die Benutzung des Formulars einfügen.
            Zum Beispiel:
            - Wie man ein neues Aufmaß erstellt
            - Wie man Artikel hinzufügt
            - Wie man Zuschläge anwendet
            usw.
            """),
            actions=[
                ft.TextButton("Schließen", on_click=self.close_help_dialog)
            ],
        )

    def open_help(self, e):
        self.show_dialog(self.help_dialog)

    def show_dialog(self, dialog):
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def close_dialog(self):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def close_settings_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def close_help_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def open_settings(self, e):
        color_options = [
            ft.dropdown.Option("BLUE"),
            ft.dropdown.Option("GREEN"),
            ft.dropdown.Option("RED"),
            ft.dropdown.Option("PURPLE"),
            ft.dropdown.Option("ORANGE")
        ]
        
        color_dropdown = ft.Dropdown(
            label="Farbschema",
            options=color_options,
            value=self.color_scheme,
            on_change=self.change_color_scheme
        )

        theme_switch = ft.Switch(
            label="Dunkles Theme",
            value=self.theme_mode == ft.ThemeMode.DARK,
            on_change=self.toggle_theme
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text("Einstellungen"),
            content=ft.Column([color_dropdown, theme_switch], tight=True),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_dialog())
            ],
        )
        
        self.show_dialog(dialog)

    def show_help(self, e):
        help_text = """
        Hilfe zur Rechnungs-App:

        1. Kopfdaten ausfüllen: Füllen Sie alle erforderlichen Felder im oberen Bereich aus.
        2. Artikel hinzufügen: Wählen Sie Bauteil, Dämmdicke, etc. und klicken Sie auf 'Artikel hinzufügen'.
        3. Artikel bearbeiten: Klicken Sie auf einen Artikel in der Liste, um ihn zu bearbeiten.
        4. Artikel löschen: Klicken Sie auf das Mülleimer-Symbol neben einem Artikel, um ihn zu löschen.
        5. Sonderleistungen: Klicken Sie auf 'Sonderleistungen', um zusätzliche Leistungen hinzuzufügen.
        6. Zuschläge: Klicken Sie auf 'Zuschläge', um Zuschläge hinzuzufügen.
        7. PDF erstellen: Klicken Sie auf 'PDF mit Preisen erstellen' oder 'PDF ohne Preise erstellen'.
        8. Neues Aufmaß: Klicken Sie auf 'Speichern und neues Aufmaß erstellen', um ein neues Aufmaß zu beginnen.

        Bei weiteren Fragen wenden Sie sich bitte an den Support.
        """
        
        dialog = ft.AlertDialog(
            title=ft.Text("Hilfe"),
            content=ft.Text(help_text),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_help_dialog(dialog))
            ],
        )
        
        self.show_dialog(dialog)

    def initialize_ui(self):
        self.add_logo_and_topbar()
        # Hier können Sie weitere UI-Initialisierungen hinzufügen

    def show_error_dialog(self, message):
        dialog = ft.AlertDialog(
        title=ft.Text("Fehler"),
        content=ft.Text(message),
        actions=[
            ft.TextButton("OK", on_click=lambda _: self.close_dialog())
        ],
    )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def add_logo_and_topbar(self):
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logos", "KAE_Logo_RGB_300dpi2.jpg")
        if os.path.exists(logo_path):
            logo = ft.Image(src=logo_path, width=100, height=40, fit=ft.ImageFit.CONTAIN)
        else:
            logo = ft.Text("KAEFER")
        
        self.topbar = ft.Container(
            content=ft.Row([
                logo,
                ft.Text("", expand=True),
                ft.IconButton(ft.icons.SETTINGS, on_click=self.open_settings),
                ft.IconButton(ft.icons.HELP_OUTLINE, on_click=self.show_help),
            ]),
            padding=10,
            bgcolor=ft.colors.SURFACE_VARIANT,
        )
      

    def disable_all_inputs(self):
        for field in self.invoice_detail_fields.values():
            field.disabled = True
        # Deaktivieren Sie auch andere relevante Felder und Buttons
        self.bemerkung_field.disabled = True
        self.zuschlaege_button.disabled = True
        self.new_aufmass_button.disabled = True
        self.save_invoice_with_pdf_button.disabled = True
        self.save_invoice_without_pdf_button.disabled = True
        # ... (andere Felder und Buttons, die deaktiviert werden sollen)

    def build(self):
        # Build the UI layout
        invoice_details = self.build_invoice_details()
        article_input = self.build_article_input()
        article_list = self.build_article_list()
        summary_and_actions = self.build_summary_and_actions()
        bemerkung_container = self.build_bemerkung_container()

        # Add the TopBar
        self.add_logo_and_topbar()

        return ft.Container(
            content=ft.Column(
                [
                    self.topbar,
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
        conn = get_db_connection()
        cursor = conn.cursor()
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
            conn.close()

    def update_date_picker_buttons(self):
        self.bestelldatum_button.text = f"Bestelldatum: {self.invoice_detail_fields['bestelldatum'].value}"
        self.ausfuehrungsbeginn_button.text = f"Ausführungsbeginn: {self.invoice_detail_fields['ausfuehrungsbeginn'].value}"
        self.ausfuehrungsende_button.text = f"Ausführungsende: {self.invoice_detail_fields['ausfuehrungsende'].value}"
        self.update()

    def create_article_input_fields(self):
        # Article input fields
        self.einheit_field = ft.TextField(label="Einheit", read_only=True, width=80)
        self.bauteil_dropdown = ft.Dropdown(label="Bauteil", on_change=self.on_bauteil_change, width=220)
        self.dn_dropdown = ft.Dropdown(label="DN", on_change=self.on_dn_change, width=80, options=[])
        self.da_dropdown = ft.Dropdown(label="DA", on_change=self.on_da_change, width=80, options=[])
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=self.on_dammdicke_change, width=140)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=self.on_taetigkeit_change, width=300)
        self.position_field = ft.TextField(label="Position", read_only=True, width=100)
        self.price_field = ft.TextField(label="Preis", read_only=True, width=80)
        self.quantity_input = ft.TextField(label="Menge", value="1", on_change=self.on_quantity_change, width=80)
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

    def on_bauteil_change(self, e):
        bauteil = e.control.value
        if bauteil:
            self.update_dn_da_fields(bauteil)
            self.update_dammdicke_options()
            self.update_einheit()
            self.update_price()
        self.update()

    def on_dn_change(self, e):
        dn = e.control.value
        if dn:
            self.update_da_options(dn)
            self.update_dammdicke_options()
            self.update_price()
        self.update()

    def on_da_change(self, e):
        da = e.control.value
        if da:
            self.update_dn_options(da)
            self.update_dammdicke_options()
            self.update_price()
        self.update()

    def on_dammdicke_change(self, e):
        self.update_price()
        self.update()

    def on_taetigkeit_change(self, e):
        self.update_price()
        self.update()

    def on_quantity_change(self, e):
        self.update_price()
        self.update()

    def update_dn_da_fields(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                cursor.execute('SELECT DISTINCT DN FROM price_list WHERE Bauteil = "Rohrleitung" ORDER BY DN')
                dn_options = [row[0] for row in cursor.fetchall()]
                self.dn_dropdown.options = [ft.dropdown.Option(str(int(dn))) for dn in dn_options]
                self.dn_dropdown.value = str(int(dn_options[0])) if dn_options else None

                cursor.execute('SELECT DISTINCT DA FROM price_list WHERE Bauteil = "Rohrleitung" ORDER BY DA')
                da_options = [row[0] for row in cursor.fetchall()]
                self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]

                if dn_options:
                    cursor.execute('SELECT MIN(DA) FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ?', (dn_options[0],))
                    first_valid_da = cursor.fetchone()[0]
                    self.da_dropdown.value = str(first_valid_da) if first_valid_da else None

                self.dn_dropdown.visible = True
                self.da_dropdown.visible = True
            else:
                self.dn_dropdown.visible = False
                self.da_dropdown.visible = False
                self.dn_dropdown.value = None
                self.da_dropdown.value = None

            self.update_dammdicke_options()
            self.update_taetigkeit_options()
        finally:
            cursor.close()
            conn.close()

    def update_da_options(self, dn):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT DA FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? ORDER BY DA', (dn,))
            da_options = [row[0] for row in cursor.fetchall()]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]
            self.da_dropdown.value = str(da_options[0]) if da_options else None
        finally:
            cursor.close()
            conn.close()

    def update_dn_options(self, da):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT DN FROM price_list WHERE Bauteil = "Rohrleitung" AND DA = ? ORDER BY DN', (da,))
            dn_options = [row[0] for row in cursor.fetchall()]
            self.dn_dropdown.options = [ft.dropdown.Option(str(int(dn))) for dn in dn_options]
            self.dn_dropdown.value = str(int(dn_options[0])) if dn_options else None
        finally:
            cursor.close()
            conn.close()

    def update_dammdicke_options(self):
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke_options = get_dammdicke_options(self, bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        self.dammdicke_dropdown.value = str(dammdicke_options[0]) if dammdicke_options else None

    def update_taetigkeit_options(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung')
            taetigkeit_options = [row[0] for row in cursor.fetchall()]
            self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeit_options]
            self.taetigkeit_dropdown.value = taetigkeit_options[0] if taetigkeit_options else None
        finally:
            cursor.close()
            conn.close()

    def create_action_buttons(self):
        button_style = ft.ButtonStyle(
            color=ft.colors.WHITE,
            bgcolor=ft.colors.BLUE_700,
            padding=10,
        )

        self.new_aufmass_button = ft.ElevatedButton(
            "Speichern und neues Aufmaß erstellen",
            on_click=self.save_and_create_new_aufmass,
            style=button_style,
            width=250,
            height=50,
        )
        
        self.save_invoice_with_pdf_button = ft.ElevatedButton(
            "PDF mit Preisen erstellen",
            on_click=self.save_invoice_with_pdf,
            style=button_style,
            width=200,
            height=50,
            disabled=True
        )
        self.save_invoice_without_pdf_button = ft.ElevatedButton(
            "PDF ohne Preise erstellen",
            on_click=self.save_invoice_without_pdf,
            style=button_style,
            width=200,
            height=50,
            disabled=True
        )
        self.back_to_main_menu_button = ft.ElevatedButton(
            "Zurück zum Hauptmenü",
            on_click=self.back_to_main_menu,
            style=button_style,
            width=200,
            height=50,
        )
        self.zuschlaege_button = ft.ElevatedButton(
            "Zuschläge",
            on_click=self.show_zuschlaege_dialog,
            style=button_style,
            width=150,
            height=50,
        )

    def create_article_list_table(self):
        # Article list table
        self.article_list_header = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Container(content=ft.Text("Position", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Bauteil", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("DN", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("DA", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Dämmdicke", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Einheit", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Tätigkeit", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Sonderleistungen", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Preis", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Menge", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Zwischensumme", size=16), alignment=ft.alignment.center)),
                ft.DataColumn(ft.Container(content=ft.Text("Aktionen", size=16), alignment=ft.alignment.center)),
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
        # Anpassen der Feldbreiten für bessere Darstellung
        field_widths = {
            'position': 100,
            'bauteil': 300,  # Breiter für lange Bauteilnamen
            'dn': 80,
            'da': 80,
            'dammdicke': 100,
            'einheit': 80,
            'taetigkeit': 300,  # Feste Breite für Tätigkeit
            'preis': 100,
            'menge': 80,
            'zwischensumme': 120
        }

        # Setze die Feldbreiten
        self.position_field.width = field_widths['position']
        self.bauteil_dropdown.width = field_widths['bauteil']
        self.dn_dropdown.width = field_widths['dn']
        self.da_dropdown.width = field_widths['da']
        self.dammdicke_dropdown.width = field_widths['dammdicke']
        self.einheit_field.width = field_widths['einheit']
        self.taetigkeit_dropdown.width = field_widths['taetigkeit']
        self.price_field.width = field_widths['preis']
        self.quantity_input.width = field_widths['menge']
        self.zwischensumme_field.width = field_widths['zwischensumme']

        # Labels in einer Zeile über den Feldern
        labels_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text("Position", size=14),
                    width=field_widths['position'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Bauteil", size=14),
                    width=field_widths['bauteil'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("DN", size=14),
                    width=field_widths['dn'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("DA", size=14),
                    width=field_widths['da'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Dämmdicke", size=14),
                    width=field_widths['dammdicke'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Einheit", size=14),
                    width=field_widths['einheit'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Tätigkeit", size=14),
                    width=field_widths['taetigkeit'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Preis", size=14),
                    width=field_widths['preis'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Menge", size=14),
                    width=field_widths['menge'],
                    alignment=ft.alignment.center
                ),
                ft.Container(
                    content=ft.Text("Zwischensumme", size=14),
                    width=field_widths['zwischensumme'],
                    alignment=ft.alignment.center
                ),
            ],
            spacing=5,
        )

        # Eingabefelder in einer Zeile
        fields_row = ft.Row(
            controls=[
                self.position_field,
                self.bauteil_dropdown,
                self.dn_dropdown,
                self.da_dropdown,
                self.dammdicke_dropdown,
                self.einheit_field,
                self.taetigkeit_dropdown,
                self.price_field,
                self.quantity_input,
                self.zwischensumme_field,
            ],
            spacing=5,
        )

        # Buttons in einer separaten Zeile
        buttons_row = ft.Row(
            controls=[
                ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
                self.sonderleistungen_button,
                self.update_position_button,
            ],
            alignment=ft.MainAxisAlignment.END,
            spacing=5,
        )

        return ft.Container(
            content=ft.Column([
                ft.Text("Artikel hinzufügen", size=20, weight=ft.FontWeight.BOLD),
                labels_row,
                fields_row,
                buttons_row,
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(bottom=20),
            width=self.page.window_width - 40,
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
                    ft.Container(
                        content=ft.Row([
                            self.zuschlaege_button,
                            self.save_invoice_with_pdf_button,
                            self.save_invoice_without_pdf_button,
                            self.new_aufmass_button,
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        expand=True
                    ),
                    self.back_to_main_menu_button,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
        )

    def delete_article_row(self, row_index):
        logging.info(f"Versuche Artikelzeile {row_index} zu löschen")
        if 0 <= row_index < len(self.article_list_header.rows):
            del self.article_list_header.rows[row_index]
            if row_index < len(self.article_summaries):
                del self.article_summaries[row_index]

            # Aktualisieren Sie die Indizes für die verbleibenden Zeilen
            for i, row in enumerate(self.article_list_header.rows):
                for cell in row.cells:
                    if isinstance(cell.content, ft.Row):
                        for control in cell.content.controls:
                            if isinstance(control, ft.IconButton):
                                if control.icon == ft.icons.DELETE:
                                    control.on_click = lambda _, r=i: self.delete_article_row(r)

            if self.edit_mode and self.edit_row_index is not None:
                if row_index < self.edit_row_index:
                    self.edit_row_index -= 1
                elif row_index == self.edit_row_index:
                    self.edit_mode = False
                    self.edit_row_index = None
                    self.update_position_button.visible = False
                    self.clear_input_fields()

            # Überprüfen Sie, ob noch Artikel übrig sind
            if len(self.article_list_header.rows) == 0:
                self.save_invoice_with_pdf_button.visible = False
                self.save_invoice_without_pdf_button.visible = False
                self.new_aufmass_button.visible = False

            self.update_total_price()
            self.update_pdf_buttons()
            self.update()
            logging.info(f"Artikelzeile {row_index} erfolgreich gelöscht")
        else:
            logging.warning(f"Ungültiger Zeilenindex beim Löschen: {row_index}")

        # Aktualisieren Sie die Positionen der verbleibenden Artikel
        self.update_article_positions()

    def update_article_positions(self):
        for i, row in enumerate(self.article_list_header.rows):
            row.cells[0].content.content.value = str(i + 1)  # Aktualisiere die Position
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
                'position': row.cells[0].content.content.value,
                'artikelbeschreibung': row.cells[1].content.content.value,
                'dn': row.cells[2].content.content.value,
                'da': row.cells[3].content.content.value,
                'dammdicke': row.cells[4].content.content.value,
                'einheit': row.cells[5].content.content.value,
                'taetigkeit': row.cells[6].content.content.value,
                'sonderleistungen': row.cells[7].content.content.value,
                'einheitspreis': row.cells[8].content.content.value,
                'quantity': row.cells[9].content.content.value,
                'zwischensumme': row.cells[10].content.content.value
            }
            invoice_data['articles'].append(article)
            try:
                zwischensumme = float(article['zwischensumme'].replace(',', '.').replace('€', '').strip() or '0')
                invoice_data['net_total'] += zwischensumme
            except ValueError:
                logging.warning(f"Ungültiger Zwischensummenwert: {article['zwischensumme']}")

        total_price = invoice_data['net_total']
        for _, faktor in invoice_data['zuschlaege']:
            total_price *= float(faktor)

        invoice_data['total_price'] = total_price

        logging.info(f"Gesammelte Rechnungsdaten: {invoice_data}")
        return invoice_data

    def get_next_aufmass_nr(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_nr = cursor.fetchone()[0]
            return str(int(max_nr or 0) + 1)
        finally:
            cursor.close()
            conn.close()

    def save_invoice_to_db(self, invoice_data):
        logging.info("Speichere Rechnung in der Datenbank")
        logging.debug(f"Rechnungsdaten: {invoice_data}")

        # Überprüfen, ob Artikel vorhanden sind
        if not invoice_data['articles']:
            self.show_error("Es können keine leeren Aufmaße ohne Artikel gespeichert werden.")
            return None

        nettobetrag = sum(float(article['zwischensumme'].replace(',', '.').replace('€', '').strip() or '0') for article in invoice_data['articles'])
        zuschlaege_summe = 0
        for zuschlag, faktor in invoice_data['zuschlaege']:
            zuschlag_betrag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag_betrag
        total_price = nettobetrag + zuschlaege_summe

        conn = get_db_connection()
        cursor = conn.cursor()
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
                new_aufmass_nr = self.get_next_aufmass_nr()
                
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

            conn.commit()
            logging.info(f"Rechnung mit ID {invoice_id} erfolgreich in der Datenbank gespeichert")
            return invoice_id
        except sqlite3.Error as e:
            logging.error(f"Datenbankfehler beim Speichern der Rechnung: {str(e)}")
            conn.rollback()
            raise Exception(f"Datenbankfehler: {str(e)}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Speichern der Rechnung: {str(e)}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_invoice_data(self, aufmass_nr):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Lade Rechnungskopfdaten
            cursor.execute('''
            SELECT client_name, bestell_nr, bestelldatum, baustelle, anlagenteil,
                   auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende, bemerkungen, zuschlaege, total_amount
            FROM invoice
            WHERE aufmass_nr = ?
            ''', (aufmass_nr,))
            invoice_data = cursor.fetchone()
            
            if invoice_data:
                self.invoice_detail_fields['client_name'].value = invoice_data[0]
                self.invoice_detail_fields['bestell_nr'].value = invoice_data[1]
                self.invoice_detail_fields['bestelldatum'].value = invoice_data[2]
                self.invoice_detail_fields['baustelle'].value = invoice_data[3]
                self.invoice_detail_fields['anlagenteil'].value = invoice_data[4]
                self.invoice_detail_fields['aufmass_nr'].value = aufmass_nr
                self.invoice_detail_fields['auftrags_nr'].value = invoice_data[5]
                self.invoice_detail_fields['ausfuehrungsbeginn'].value = invoice_data[6]
                self.invoice_detail_fields['ausfuehrungsende'].value = invoice_data[7]
                self.bemerkung_field.value = invoice_data[8]
                
                # Lade Zuschläge
                self.selected_zuschlaege = []
                if invoice_data[9]:
                    zuschlaege = invoice_data[9].split(',')
                    for zuschlag in zuschlaege:
                        bezeichnung, faktor = zuschlag.split(':')
                        self.selected_zuschlaege.append((bezeichnung, float(faktor)))
                
                # Lade Artikeldaten
                cursor.execute('''
                    SELECT position, Bauteil, DN, DA, Size, taetigkeit, Unit, Value, quantity, zwischensumme, sonderleistungen
                    FROM invoice_items
                    WHERE invoice_id = (SELECT id FROM invoice WHERE aufmass_nr = ?)
                    ORDER BY position
                ''', (aufmass_nr,))
                items = cursor.fetchall()
                
                self.article_list_header.rows.clear()
                self.article_summaries.clear()
                
                for item in items:
                    row_index = len(self.article_list_header.rows)
                    new_row = ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Container(content=ft.Text(item[0], size=16), alignment=ft.alignment.center)),  # Position
                            ft.DataCell(ft.Container(content=ft.Text(item[1], size=16), alignment=ft.alignment.center)),  # Bauteil
                            ft.DataCell(ft.Container(content=ft.Text(item[2], size=16), alignment=ft.alignment.center)),  # DN
                            ft.DataCell(ft.Container(content=ft.Text(item[3], size=16), alignment=ft.alignment.center)),  # DA
                            ft.DataCell(ft.Container(content=ft.Text(item[4], size=16), alignment=ft.alignment.center)),  # Dämmdicke
                            ft.DataCell(ft.Container(content=ft.Text(item[6], size=16), alignment=ft.alignment.center)),  # Einheit
                            ft.DataCell(ft.Container(content=ft.Text(item[5], size=16), alignment=ft.alignment.center)),  # Tätigkeit
                            ft.DataCell(ft.Container(content=ft.Text(item[10], size=16), alignment=ft.alignment.center)),  # Sonderleistungen
                            ft.DataCell(ft.Container(content=ft.Text(f"{item[7]:.2f}", size=16), alignment=ft.alignment.center)),  # Preis
                            ft.DataCell(ft.Container(content=ft.Text(str(item[8]), size=16), alignment=ft.alignment.center)),  # Menge
                            ft.DataCell(ft.Container(content=ft.Text(f"{item[9]:.2f}", size=16), alignment=ft.alignment.center)),  # Zwischensumme
                            ft.DataCell(
                                    ft.Row([
                                        ft.IconButton(
                                            icon=ft.icons.DELETE,
                                            icon_color="red500",
                                            on_click=lambda _, row=row_index: self.delete_article_row(row)
                                        )
                                    ], alignment=ft.MainAxisAlignment.CENTER)
                                )
                        ],
                        on_select_changed=lambda e, index=row_index: self.edit_article_row(index)
                    )
                    self.article_list_header.rows.append(new_row)
                    
                    summary_data = {
                        'zwischensumme': float(item[9]) if item[9] else 0,
                        'sonderleistungen': item[10].split(', ') if item[10] else []
                    }
                    self.article_summaries.append(summary_data)
                
                if self.article_list_header.rows:
                    self.save_invoice_with_pdf_button.visible = True
                    self.save_invoice_without_pdf_button.visible = True
                    self.new_aufmass_button.visible = True
                else:
                    self.save_invoice_with_pdf_button.visible = False
                    self.save_invoice_without_pdf_button.visible = False
                    self.new_aufmass_button.visible = False
                
                self.update_total_price()
                self.update_pdf_buttons()
                self.update_date_picker_buttons()
                self.pdf_generated = True
                self.update_topbar()  # Hier hinzugefügt
                self.update()

                # Nachdem alle Daten geladen wurden, aktivieren Sie die Eingabefelder
                self.enable_all_inputs()

                self.update()
            else:
                logging.warning(f"Keine Rechnung mit Aufmaß-Nr. {aufmass_nr} gefunden")
        except Exception as e:
            logging.error(f"Fehler beim Laden der Rechnungsdaten: {str(e)}")
        finally:
            cursor.close()
            conn.close()

    def enable_all_inputs(self):
        for field in self.invoice_detail_fields.values():
            if hasattr(field, 'disabled'):
                field.disabled = False
        if hasattr(self.bemerkung_field, 'disabled'):
            self.bemerkung_field.disabled = False
        if hasattr(self.zuschlaege_button, 'disabled'):
            self.zuschlaege_button.disabled = False
        if hasattr(self.new_aufmass_button, 'disabled'):
            self.new_aufmass_button.disabled = False
        if hasattr(self.save_invoice_with_pdf_button, 'disabled'):
            self.save_invoice_with_pdf_button.disabled = False
        if hasattr(self.save_invoice_without_pdf_button, 'disabled'):
            self.save_invoice_without_pdf_button.disabled = False
        # Aktiviere andere relevante Felder und Buttons
        self.update()

    def enable_header_fields(self):
        for field in self.invoice_detail_fields.values():
            if hasattr(field, 'disabled'):
                field.disabled = False
        if hasattr(self.bemerkung_field, 'disabled'):
            self.bemerkung_field.disabled = False
        self.update()


    def save_and_create_new_aufmass(self, e):
        # Zuerst das aktuelle Aufmaß speichern
        invoice_data = self.get_invoice_data()
        self.save_invoice_to_db(invoice_data)
        
        # Dann ein neues Aufmaß erstellen
        self.reset_form()
        
        # Aktualisieren Sie die Benutzeroberfläche
        self.update()

    def reset_form(self):
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

        # Setzen Sie die Aufmaß-Nummer auf die nächste verfügbare Nummer
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

        # Setzen Sie die Buttons auf sichtbar
        self.save_invoice_with_pdf_button.visible = True
        self.save_invoice_without_pdf_button.visible = True
        self.new_aufmass_button.visible = True

        # Aktualisieren Sie die Gesamtpreise
        self.update_total_price()
        self.update_pdf_buttons()
        self.update_topbar()

        # Aktualisieren Sie die Benutzeroberfläche
        self.update()
        self.show_snack_bar("Neues Aufmaß erstellt. Kopfdaten wurden beibehalten.")

    def on_bestelldatum_change(self, e):
        self.update_date_field(e, 'bestelldatum', self.bestelldatum_button)

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

    def on_ausfuehrungsbeginn_change(self, e):
        self.update_date_field(e, 'ausfuehrungsbeginn', self.ausfuehrungsbeginn_button)

    def on_ausfuehrungsende_change(self, e):
        self.update_date_field(e, 'ausfuehrungsende', self.ausfuehrungsende_button)

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

    def update_article_row(self, e):
        """Aktualisiert eine bestehende Artikelzeile im Bearbeitungsmodus"""
        if self.edit_mode and self.edit_row_index is not None:
            if 0 <= self.edit_row_index < len(self.article_list_header.rows):
                sonderleistungen = ", ".join([sl[0] for sl in self.selected_sonderleistungen])
                updated_row = ft.DataRow(
                    cells=[
                    ft.DataCell(ft.Container(content=ft.Text(self.position_field.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.bauteil_dropdown.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "", size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "", size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.dammdicke_dropdown.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.einheit_field.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.taetigkeit_dropdown.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(sonderleistungen, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.price_field.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.quantity_input.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(ft.Container(content=ft.Text(self.zwischensumme_field.value, size=16), alignment=ft.alignment.center)),
                    ft.DataCell(
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                icon_color="red500",
                                on_click=lambda _, row=self.edit_row_index: self.delete_article_row(row)
                            )
                        ], alignment=ft.MainAxisAlignment.CENTER)
                    )
                ],
                on_select_changed=lambda e, index=self.edit_row_index: self.edit_article_row(index)
            )

            self.article_list_header.rows[self.edit_row_index] = updated_row
            self.article_summaries[self.edit_row_index] = {
                'zwischensumme': float(self.zwischensumme_field.value.replace(',', '.')),
                'sonderleistungen': self.selected_sonderleistungen.copy()
            }



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
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_nr = cursor.fetchone()[0]
            return str(int(max_nr or 0) + 1)
        finally:
            cursor.close()
            conn.close()

    def get_current_aufmass_nr(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_id = cursor.fetchone()[0]
            return str(max_id) if max_id else "0"
        finally:
            cursor.close()
            conn.close()

    def load_invoice_options(self):
        for field in self.invoice_detail_fields:
            if field == 'aufmass_nr':
                continue
            options = self.get_from_cache_or_db(f"invoice_options_{field}", f"SELECT DISTINCT {field} FROM invoice WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
            self.invoice_detail_fields[field].options = [ft.dropdown.Option(str(option[0])) for option in options]
            self.invoice_detail_fields[field].options.append(ft.dropdown.Option("Neuer Eintrag"))

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
            cursor.close()
            conn.close()
        return self.cache[key]

    def load_data(self):
        # Load necessary data from the database
        self.load_faktoren("Sonderleistung")
        self.load_faktoren("Zuschläge")
        self.update_field_visibility()
        self.update_einheit()
        self.update_price()

    def load_faktoren(self, art):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
            faktoren = cursor.fetchall()
            if art == "Sonderleistung":
                self.sonderleistungen_options = [(bezeichnung, float(faktor)) for bezeichnung, faktor in faktoren]
            elif art == "Zuschläge":
                self.zuschlaege_options = [(bezeichnung, float(faktor)) for bezeichnung, faktor in faktoren]
        finally:
            cursor.close()
            conn.close()

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
        return self.is_rohrleitung(bauteil) or self.is_formteil(bauteil)

    def is_rohrleitung(self, bauteil):
        return bauteil is not None and bauteil.lower() == "rohrleitung"

    def is_formteil(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ? LIMIT 1', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            conn.close()

    def auto_fill_rohrleitung_or_formteil(self, bauteil):
        conn = get_db_connection()
        cursor = conn.cursor()
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
            conn.close()

    def update_einheit(self):
        bauteil = self.bauteil_dropdown.value
        if bauteil:
            if self.is_formteil(bauteil):
                self.einheit_field.value = "m²"
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute('SELECT Unit FROM price_list WHERE Bauteil = ? LIMIT 1', (bauteil,))
                    result = cursor.fetchone()
                    if result:
                        self.einheit_field.value = result[0]
                    else:
                        self.einheit_field.value = ""
                finally:
                    cursor.close()
                    conn.close()
        else:
            self.einheit_field.value = ""
        self.update()

    def update_dn_fields(self, e):
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT MIN(DA) FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ?', (dn,))
                first_valid_da = cursor.fetchone()[0]
                if first_valid_da:
                    self.da_dropdown.value = str(first_valid_da)
                else:
                    self.da_dropdown.value = None
            finally:
                cursor.close()
                conn.close()
        self.update_dammdicke_options()
        update_price(self)
        self.update()

    def update_da_fields(self, e):
        bauteil = self.bauteil_dropdown.value
        da = self.da_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT MIN(DN) FROM price_list WHERE Bauteil = "Rohrleitung" AND DA = ?', (da,))
                first_valid_dn = cursor.fetchone()[0]
                if first_valid_dn:
                    self.dn_dropdown.value = str(int(first_valid_dn))
                else:
                    self.dn_dropdown.value = None
            finally:
                cursor.close()
                conn.close()
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
                row.cells[1].content.content.value,  # Bauteil
                row.cells[2].content.content.value,  # DN
                row.cells[3].content.content.value,  # DA
                row.cells[4].content.content.value,  # Dämmdicke
                row.cells[6].content.content.value,  # Tätigkeit
                row.cells[7].content.content.value,  # Sonderleistungen
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
        position = get_positionsnummer(self, self.bauteil_dropdown.value, self.dammdicke_dropdown.value, self.dn_dropdown.value if self.dn_dropdown.visible else None, self.da_dropdown.value if self.da_dropdown.visible else None, self.current_category)
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke = self.dammdicke_dropdown.value
        einheit = self.einheit_field.value
        taetigkeit = self.taetigkeit_dropdown.value
        menge = self.quantity_input.value
        preis = self.price_field.value
        sonderleistungen = ", ".join([sl[0] for sl in self.selected_sonderleistungen])
        zwischensumme = self.zwischensumme_field.value

        new_row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Container(content=ft.Text(position, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(bauteil, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(dn, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(da, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(dammdicke, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(einheit, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(taetigkeit, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(sonderleistungen, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(preis, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(menge, size=16), alignment=ft.alignment.center)),
                ft.DataCell(ft.Container(content=ft.Text(zwischensumme, size=16), alignment=ft.alignment.center)),
                ft.DataCell(
                    ft.Row([
                        ft.IconButton(
                            icon=ft.icons.DELETE,
                            icon_color="red500",
                            on_click=lambda _, row=len(self.article_list_header.rows): self.delete_article_row(row)
                        )
                    ], alignment=ft.MainAxisAlignment.CENTER)
                )
            ],
            on_select_changed=lambda e, row_index=len(self.article_list_header.rows): self.edit_article_row(row_index)
        )
        self.article_list_header.rows.append(new_row)

        summary_data = {
            'zwischensumme': float(zwischensumme.replace(',', '.')),
            'sonderleistungen': self.selected_sonderleistungen.copy()
        }
        self.article_summaries.append(summary_data)

        # Machen Sie die Buttons sichtbar, nachdem der erste Artikel hinzugefügt wurde
        self.save_invoice_with_pdf_button.visible = True
        self.save_invoice_without_pdf_button.visible = True
        self.new_aufmass_button.visible = True

        self.update_total_price()
        self.clear_input_fields()
        self.update_pdf_buttons()
        self.page.update()
        logging.info(f"Neue Artikelzeile hinzugefügt: {position}")

    def edit_article_row(self, row_index):
        logging.info(f"Bearbeite Artikelzeile {row_index}")
        if 0 <= row_index < len(self.article_list_header.rows):
            row = self.article_list_header.rows[row_index]
            self.edit_mode = True
            self.edit_row_index = row_index
            self.update_position_button.visible = True

            # Füllen Sie die Eingabefelder mit den Werten aus der ausgewählten Zeile
            self.position_field.value = row.cells[0].content.content.value
            self.bauteil_dropdown.value = row.cells[1].content.content.value
            self.dn_dropdown.value = row.cells[2].content.content.value
            self.da_dropdown.value = row.cells[3].content.content.value
            self.dammdicke_dropdown.value = row.cells[4].content.content.value
            self.einheit_field.value = row.cells[5].content.content.value
            self.taetigkeit_dropdown.value = row.cells[6].content.content.value

            # Behandeln Sie Sonderleistungen
            sonderleistungen_str = row.cells[7].content.content.value
            self.selected_sonderleistungen = []
            if sonderleistungen_str:
                sonderleistungen = sonderleistungen_str.split(', ')
                for sl in sonderleistungen:
                    faktor = self.get_sonderleistung_faktor(sl)
                    self.selected_sonderleistungen.append((sl, faktor))

            self.price_field.value = row.cells[8].content.content.value.replace(' €', '')
            self.quantity_input.value = row.cells[9].content.content.value
            self.zwischensumme_field.value = row.cells[10].content.content.value.replace(' €', '')

            # Aktualisieren Sie die Sichtbarkeit der DN/DA Felder
            self.dn_dropdown.visible = bool(self.dn_dropdown.value)
            self.da_dropdown.visible = bool(self.da_dropdown.value)

            # Aktualisieren Sie den Sonderleistungen-Button
            self.update_sonderleistungen_button()

            # Aktualisieren Sie die Benutzeroberfläche
            self.update()

            # Scrollen Sie zu den Eingabefeldern
            self.page.update()
        else:
            logging.warning(f"Ungültiger Zeilenindex beim Bearbeiten: {row_index}")

    def get_sonderleistung_faktor(self, sonderleistung):
        for sl, faktor in self.sonderleistungen_options:
            if sl == sonderleistung:
                return faktor
        return 1.0  # Standardfaktor, falls nicht gefunden

    def update_article_row(self, e):
        if self.edit_mode and self.edit_row_index is not None:
            if 0 <= self.edit_row_index < len(self.article_list_header.rows):
                sonderleistungen = ", ".join([sl[0] for sl in self.selected_sonderleistungen])
                updated_row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Container(content=ft.Text(self.position_field.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.bauteil_dropdown.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "", size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "", size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.dammdicke_dropdown.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.einheit_field.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.taetigkeit_dropdown.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(sonderleistungen, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.price_field.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.quantity_input.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(ft.Container(content=ft.Text(self.zwischensumme_field.value, size=16), alignment=ft.alignment.center)),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.DELETE,
                                    icon_color="red500",
                                    on_click=lambda _, row=self.edit_row_index: self.delete_article_row(row)
                                )
                            ], alignment=ft.MainAxisAlignment.CENTER)
                        )
                    ],
                    on_select_changed=lambda e, index=self.edit_row_index: self.edit_article_row(index)
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

    def back_to_main_menu(self, e=None):
        if self.page:
            if hasattr(self.page, 'go'):
                # Setze das Logo zurück
                self.reset_logo()
                # Navigiere zum Hauptmenü
                self.page.go('/')
            else:
                logging.error("Page object does not have 'go' method")
        else:
            logging.error("Page object is None in InvoiceForm")

    def reset_logo(self):
        if hasattr(self.page, 'appbar'):
            logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logos", "KAE_Logo_RGB_300dpi2.jpg")
            if os.path.exists(logo_path):
                self.page.appbar.leading = ft.Image(src=logo_path, width=100, height=40, fit=ft.ImageFit.CONTAIN)
            else:
                self.page.appbar.leading = ft.Text("KAEFER")
            self.page.appbar.title = ft.Text("")  # Setze den Titel zurück
            self.page.update()

    def update_topbar(self):
        if self.topbar:
            aufmass_nr = self.invoice_detail_fields['aufmass_nr'].value
            title = f"Aufmaß Nr. {aufmass_nr}" if aufmass_nr else "Neues Aufmaß"
            self.topbar.content.controls[1] = ft.Text(title, expand=True)
            self.update()
            
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

        # Setzen Sie die Aufmaß-Nummer nur zurück, wenn zuvor eine Rechnung erstellt wurde
        if self.pdf_generated:
            self.next_aufmass_nr = str(int(self.next_aufmass_nr) + 1)
            self.invoice_detail_fields['aufmass_nr'].value = self.next_aufmass_nr
            self.pdf_generated = False
        else:
            # Wenn keine Rechnung erstellt wurde, behalten Sie die aktuelle Aufmaß-Nummer bei
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

        # Setzen Sie die Buttons auf unsichtbar
        self.save_invoice_with_pdf_button.visible = False
        self.save_invoice_without_pdf_button.visible = False
        self.new_aufmass_button.visible = False

        # Aktualisieren Sie die Gesamtpreise
        self.update_total_price()
        self.update_pdf_buttons()
        self.update_topbar()  # Hier hinzugefügt

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

    def create_pdf(self, include_prices=True, force_new=False):
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
                self.update_topbar()  # Aktualisiere die TopBar nach der PDF-Erstellung
            else:
                raise FileNotFoundError(f"PDF-Datei wurde nicht erstellt: {filepath}")

        except Exception as ex:
            logging.error(f"Fehler beim Erstellen des PDFs: {str(ex)}", exc_info=True)
            self.show_snack_bar(f"Fehler beim Erstellen des PDFs: {str(ex)}")
        finally:
            self.update_pdf_buttons()  # Stelle sicher, dass die Buttons in jedem Fall aktualisiert werden
            self.update_topbar()  # Stelle sicher, dass die TopBar in jedem Fall aktualisiert wird
            self.update()

    def check_existing_pdf(self, invoice_id):
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        for filename in os.listdir(downloads_dir):
            if filename.startswith(f"Rechnung_{invoice_id}_") or filename.startswith(f"Auftragsbestätigung_{invoice_id}_"):
                return os.path.join(downloads_dir, filename)
        return None

    def update_pdf_buttons(self):
        if hasattr(self, 'save_invoice_with_pdf_button'):
            self.save_invoice_with_pdf_button.disabled = False
        if hasattr(self, 'save_invoice_without_pdf_button'):
            self.save_invoice_without_pdf_button.disabled = False
        self.update()

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
                float(row.cells[10].content.content.value.replace(',', '.').replace('€', '').strip() or '0')
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
        logging.info(f"Versuche Artikelzeile {row_index} zu löschen")
        if 0 <= row_index < len(self.article_list_header.rows):
            del self.article_list_header.rows[row_index]
            if row_index < len(self.article_summaries):
                del self.article_summaries[row_index]

            # Aktualisieren Sie die Indizes für die verbleibenden Zeilen
            for i, row in enumerate(self.article_list_header.rows):
                for cell in row.cells:
                    if isinstance(cell.content, ft.Row):
                        for control in cell.content.controls:
                            if isinstance(control, ft.IconButton):
                                if control.icon == ft.icons.DELETE:
                                    control.on_click = lambda _, r=i: self.delete_article_row(r)

            if self.edit_mode and self.edit_row_index is not None:
                if row_index < self.edit_row_index:
                    self.edit_row_index -= 1
                elif row_index == self.edit_row_index:
                    self.edit_mode = False
                    self.edit_row_index = None
                    self.update_position_button.visible = False
                    self.clear_input_fields()

            # Überprüfen Sie, ob noch Artikel übrig sind
            if len(self.article_list_header.rows) == 0:
                self.save_invoice_with_pdf_button.visible = False
                self.save_invoice_without_pdf_button.visible = False
                self.new_aufmass_button.visible = False

            self.update_total_price()
            self.update_pdf_buttons()
            self.update()
            logging.info(f"Artikelzeile {row_index} erfolgreich gelöscht")
        else:
            logging.warning(f"Ungültiger Zeilenindex beim Löschen: {row_index}")

        # Aktualisieren Sie die Positionen der verbleibenden Artikel
        self.update_article_positions()

    def update_article_positions(self):
        for i, row in enumerate(self.article_list_header.rows):
            row.cells[0].content.content.value = str(i + 1)  # Aktualisiere die Position
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
                'position': row.cells[0].content.content.value,
                'artikelbeschreibung': row.cells[1].content.content.value,
                'dn': row.cells[2].content.content.value,
                'da': row.cells[3].content.content.value,
                'dammdicke': row.cells[4].content.content.value,
                'einheit': row.cells[5].content.content.value,
                'taetigkeit': row.cells[6].content.content.value,
                'sonderleistungen': row.cells[7].content.content.value,
                'einheitspreis': row.cells[8].content.content.value,
                'quantity': row.cells[9].content.content.value,
                'zwischensumme': row.cells[10].content.content.value
            }
            invoice_data['articles'].append(article)
            try:
                zwischensumme = float(article['zwischensumme'].replace(',', '.').replace('€', '').strip() or '0')
                invoice_data['net_total'] += zwischensumme
            except ValueError:
                logging.warning(f"Ungültiger Zwischensummenwert: {article['zwischensumme']}")

        total_price = invoice_data['net_total']
        for _, faktor in invoice_data['zuschlaege']:
            total_price *= float(faktor)

        invoice_data['total_price'] = total_price

        logging.info(f"Gesammelte Rechnungsdaten: {invoice_data}")
        return invoice_data

    def get_next_aufmass_nr(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_nr = cursor.fetchone()[0]
            return str(int(max_nr or 0) + 1)
        finally:
            cursor.close()
            conn.close()

    def save_invoice_to_db(self, invoice_data):
        logging.info("Speichere Rechnung in der Datenbank")
        logging.debug(f"Rechnungsdaten: {invoice_data}")

        # Überprüfen, ob Artikel vorhanden sind
        if not invoice_data['articles']:
            self.show_error("Es können keine leeren Aufmaße ohne Artikel gespeichert werden.")
            return None

        nettobetrag = sum(float(article['zwischensumme'].replace(',', '.').replace('€', '').strip() or '0') for article in invoice_data['articles'])
        zuschlaege_summe = 0
        for zuschlag, faktor in invoice_data['zuschlaege']:
            zuschlag_betrag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag_betrag
        total_price = nettobetrag + zuschlaege_summe

        conn = get_db_connection()
        cursor = conn.cursor()
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
                new_aufmass_nr = self.get_next_aufmass_nr()
                
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

            conn.commit()
            logging.info(f"Rechnung mit ID {invoice_id} erfolgreich in der Datenbank gespeichert")
            return invoice_id
        except sqlite3.Error as e:
            logging.error(f"Datenbankfehler beim Speichern der Rechnung: {str(e)}")
            conn.rollback()
            raise Exception(f"Datenbankfehler: {str(e)}")
        except Exception as e:
            logging.error(f"Unerwarteter Fehler beim Speichern der Rechnung: {str(e)}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_invoice_data(self, aufmass_nr):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Lade Rechnungskopfdaten
            cursor.execute('''
            SELECT client_name, bestell_nr, bestelldatum, baustelle, anlagenteil,
                   auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende, bemerkungen, zuschlaege, total_amount
            FROM invoice
            WHERE aufmass_nr = ?
            ''', (aufmass_nr,))
            invoice_data = cursor.fetchone()
            
            if invoice_data:
                self.invoice_detail_fields['client_name'].value = invoice_data[0]
                self.invoice_detail_fields['bestell_nr'].value = invoice_data[1]
                self.invoice_detail_fields['bestelldatum'].value = invoice_data[2]
                self.invoice_detail_fields['baustelle'].value = invoice_data[3]
                self.invoice_detail_fields['anlagenteil'].value = invoice_data[4]
                self.invoice_detail_fields['aufmass_nr'].value = aufmass_nr
                self.invoice_detail_fields['auftrags_nr'].value = invoice_data[5]
                self.invoice_detail_fields['ausfuehrungsbeginn'].value = invoice_data[6]
                self.invoice_detail_fields['ausfuehrungsende'].value = invoice_data[7]
                self.bemerkung_field.value = invoice_data[8]
                
                # Lade Zuschläge
                self.selected_zuschlaege = []
                if invoice_data[9]:
                    zuschlaege = invoice_data[9].split(',')
                    for zuschlag in zuschlaege:
                        bezeichnung, faktor = zuschlag.split(':')
                        self.selected_zuschlaege.append((bezeichnung, float(faktor)))
                
                # Lade Artikeldaten
                cursor.execute('''
                    SELECT position, Bauteil, DN, DA, Size, taetigkeit, Unit, Value, quantity, zwischensumme, sonderleistungen
                    FROM invoice_items
                    WHERE invoice_id = (SELECT id FROM invoice WHERE aufmass_nr = ?)
                    ORDER BY position
                ''', (aufmass_nr,))
                items = cursor.fetchall()
                
                self.article_list_header.rows.clear()
                self.article_summaries.clear()
                
                for item in items:
                    row_index = len(self.article_list_header.rows)
                    new_row = ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Container(content=ft.Text(item[0], size=16), alignment=ft.alignment.center)),  # Position
                            ft.DataCell(ft.Container(content=ft.Text(item[1], size=16), alignment=ft.alignment.center)),  # Bauteil
                            ft.DataCell(ft.Container(content=ft.Text(item[2], size=16), alignment=ft.alignment.center)),  # DN
                            ft.DataCell(ft.Container(content=ft.Text(item[3], size=16), alignment=ft.alignment.center)),  # DA
                            ft.DataCell(ft.Container(content=ft.Text(item[4], size=16), alignment=ft.alignment.center)),  # Dämmdicke
                            ft.DataCell(ft.Container(content=ft.Text(item[6], size=16), alignment=ft.alignment.center)),  # Einheit
                            ft.DataCell(ft.Container(content=ft.Text(item[5], size=16), alignment=ft.alignment.center)),  # Tätigkeit
                            ft.DataCell(ft.Container(content=ft.Text(item[10], size=16), alignment=ft.alignment.center)),  # Sonderleistungen
                            ft.DataCell(ft.Container(content=ft.Text(f"{item[7]:.2f}", size=16), alignment=ft.alignment.center)),  # Preis
                            ft.DataCell(ft.Container(content=ft.Text(str(item[8]), size=16), alignment=ft.alignment.center)),  # Menge
                            ft.DataCell(ft.Container(content=ft.Text(f"{item[9]:.2f}", size=16), alignment=ft.alignment.center)),  # Zwischensumme
                            ft.DataCell(
                                    ft.Row([
                                        ft.IconButton(
                                            icon=ft.icons.DELETE,
                                            icon_color="red500",
                                            on_click=lambda _, row=row_index: self.delete_article_row(row)
                                        )
                                    ], alignment=ft.MainAxisAlignment.CENTER)
                                )
                        ],
                        on_select_changed=lambda e, index=row_index: self.edit_article_row(index)
                    )
                    self.article_list_header.rows.append(new_row)
                    
                    summary_data = {
                        'zwischensumme': float(item[9]) if item[9] else 0,
                        'sonderleistungen': item[10].split(', ') if item[10] else []
                    }
                    self.article_summaries.append(summary_data)
                
                if self.article_list_header.rows:
                    self.save_invoice_with_pdf_button.visible = True
                    self.save_invoice_without_pdf_button.visible = True
                    self.new_aufmass_button.visible = True
                else:
                    self.save_invoice_with_pdf_button.visible = False
                    self.save_invoice_without_pdf_button.visible = False
                    self.new_aufmass_button.visible = False
                
                self.update_total_price()
                self.update_pdf_buttons()
                self.update_date_picker_buttons()
                self.pdf_generated = True
                self.update_topbar()  # Hier hinzugefügt
                self.update()

                # Nachdem alle Daten geladen wurden, aktivieren Sie die Eingabefelder
                self.enable_all_inputs()

                self.update()
            else:
                logging.warning(f"Keine Rechnung mit Aufmaß-Nr. {aufmass_nr} gefunden")
        except Exception as e:
            logging.error(f"Fehler beim Laden der Rechnungsdaten: {str(e)}")
        finally:
            cursor.close()
            conn.close()

    def enable_all_inputs(self):
        for field in self.invoice_detail_fields.values():
            if hasattr(field, 'disabled'):
                field.disabled = False
        if hasattr(self.bemerkung_field, 'disabled'):
            self.bemerkung_field.disabled = False
        if hasattr(self.zuschlaege_button, 'disabled'):
            self.zuschlaege_button.disabled = False
        if hasattr(self.new_aufmass_button, 'disabled'):
            self.new_aufmass_button.disabled = False
        if hasattr(self.save_invoice_with_pdf_button, 'disabled'):
            self.save_invoice_with_pdf_button.disabled = False
        if hasattr(self.save_invoice_without_pdf_button, 'disabled'):
            self.save_invoice_without_pdf_button.disabled = False
        # Aktiviere andere relevante Felder und Buttons
        self.update()

    def enable_header_fields(self):
        for field in self.invoice_detail_fields.values():
            if hasattr(field, 'disabled'):
                field.disabled = False
        if hasattr(self.bemerkung_field, 'disabled'):
            self.bemerkung_field.disabled = False
        self.update()


    def save_and_create_new_aufmass(self, e):
        # Zuerst das aktuelle Aufmaß speichern
        invoice_data = self.get_invoice_data()
        self.save_invoice_to_db(invoice_data)
        
        # Dann ein neues Aufmaß erstellen
        self.reset_form()
        
        # Aktualisieren Sie die Benutzeroberfläche
        self.update()

    def reset_form(self):
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

        # Setzen Sie die Aufmaß-Nummer auf die nächste verfügbare Nummer
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

        # Setzen Sie die Buttons auf sichtbar
        self.save_invoice_with_pdf_button.visible = True
        self.save_invoice_without_pdf_button.visible = True
        self.new_aufmass_button.visible = True

        # Aktualisieren Sie die Gesamtpreise
        self.update_total_price()
        self.update_pdf_buttons()
        self.update_topbar()

        # Aktualisieren Sie die Benutzeroberfläche
        self.update()
        self.show_snack_bar("Neues Aufmaß erstellt. Kopfdaten wurden beibehalten.")
    
    def change_color_scheme(self, e):
        color = e.control.value
        self.set_color_scheme(color)
        self.update_theme()
    
    def change_color_scheme(self, e):
        self.color_scheme = e.control.value
        self.update_theme()

    def toggle_theme(self, e):
        self.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self.update_theme()

    def update_theme(self):
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=getattr(ft.colors, self.color_scheme),
                on_primary=ft.colors.WHITE,
            )
        )
        self.page.bgcolor = ft.colors.WHITE if self.theme_mode == ft.ThemeMode.LIGHT else ft.colors.BLACK
        self.update()
        self.page.update()

    def close_settings_dialog(self, dialog):
        dialog.open = False
        self.update()   

    def close_help_dialog(self, dialog):
        dialog.open = False
        self.update()

    def load_color_scheme(self):
        self.color_scheme = self.get_color_scheme()
        self.update_theme()

    def get_color_scheme(self):
        return self.color_scheme
    
    def set_color_scheme(self, color):
        if hasattr(self.page, 'client_storage'):
            self.page.client_storage.set("color_scheme", color)

    def update_summary_buttons(self):
        if self.article_summaries:
            self.save_invoice_with_pdf_button.visible = True
            self.save_invoice_without_pdf_button.visible = True
        else:
            self.save_invoice_with_pdf_button.visible = False
            self.save_invoice_without_pdf_button.visible = False

    def theme_changed(self, e):
        self.update_summary_buttons()
        self.update()

    def theme_changed_callback(self, e):
        self.theme_changed(e)

    def update_summary_buttons_callback(self, e):
        self.update_summary_buttons(e)

    def show_settings(self, e):
        self.open_settings(e)

    def show_help(self, e):
        self.open_help(e)

    def open_help(self, e):
        self.show_dialog(self.help_dialog)  

    def show_error_dialog(self, message):
        dialog = ft.AlertDialog(
            title=ft.Text("Fehler"),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda _: self.close_error_dialog(dialog))],
        )
        self.show_dialog(dialog)

    def close_error_dialog(self, dialog):
        dialog.open = False
        self.update()

    def help_dialog_callback(self, e):
        self.show_help(e)

    def settings_dialog_callback(self, e):
        self.show_settings(e)

    def settings_dialog_close_callback(self, e):
        self.close_settings_dialog(e)

    def settings_dialog_change_color_scheme_callback(self, e):
        self.change_color_scheme(e)

    def settings_dialog_load_color_scheme_callback(self, e):
        self.load_color_scheme(e)
