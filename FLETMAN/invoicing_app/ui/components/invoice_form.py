import logging
import sqlite3
import flet as ft
import os
from datetime import datetime
from ui.components.topbar import TopBar
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
        self.aufmass_nr = aufmass_nr
        self.is_preview = is_preview
        self.color_scheme = initial_color_scheme
        self.theme_mode = initial_theme_mode
        self.invoice_detail_fields = {}
        self.article_list_header = None
        self.article_summaries = []
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
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
        self.load_color_scheme()
        self.update_summary_buttons()

        # Add the TopBar
        self.add_logo_and_topbar()

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

    def create_total_section(self):
        self.total_price_text = ft.Text("Gesamtpreis: 0.00 €", size=20, weight=ft.FontWeight.BOLD)
        return ft.Column([self.total_price_text])

    def close_settings_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def close_help_dialog(self, e):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def change_color_scheme(self, e):
        color_scheme = e.control.value
        self.page.theme.color_scheme = ft.ColorScheme(color_scheme)
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
                ft.TextButton("Schließen", on_click=lambda _: self.close_dialog())
            ],
        )
        
        self.show_dialog(dialog)

    def update_theme(self):
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=getattr(ft.colors, self.color_scheme),
                on_primary=ft.colors.WHITE,
            )
        )
        self.page.theme_mode = self.theme_mode
        self.page.update()

    def update_topbar(self):
        aufmass_nr = self.invoice_detail_fields['aufmass_nr'].value if 'aufmass_nr' in self.invoice_detail_fields else "Neu"
        self.topbar.update_title(f"Aufmaß Nr. {aufmass_nr}")

    def save_invoice_with_pdf(self, e):
        invoice_data = self.get_invoice_data()
        self.save_invoice_to_db(invoice_data)
        generate_pdf(invoice_data, include_prices=True)
        self.show_snack_bar("Rechnung mit PDF gespeichert")

    def save_invoice_without_pdf(self, e):
        invoice_data = self.get_invoice_data()
        self.save_invoice_to_db(invoice_data)
        self.show_snack_bar("Rechnung ohne PDF gespeichert")

    def reset_form(self, e):
        for field in self.invoice_detail_fields.values():
            if not isinstance(field, ft.TextField) or not field.read_only:
                field.value = None
        self.invoice_detail_fields['aufmass_nr'].value = self.get_next_aufmass_nr()
        self.article_list_header.rows.clear()
        self.article_summaries.clear()
        self.selected_sonderleistungen.clear()
        self.selected_zuschlaege.clear()
        self.update_total_price()
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
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=5, wrap=True)

        button_row = ft.Row([
            ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
            self.sonderleistungen_button,
            self.update_position_button,
        ], alignment=ft.MainAxisAlignment.END, spacing=10)

        return ft.Container(
            content=ft.Column([
                ft.Text("Artikel hinzufügen", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Column([self.article_input_row], expand=True),
                    button_row
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
            padding=20,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            margin=ft.margin.only(bottom=20),
            width=self.page.window_width - 40,  # Breite des Containers anpassen
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

    def update_price(self, e=None):
        bauteil = self.bauteil_dropdown.value
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        einheit = self.einheit_dropdown.value
        menge = self.menge_field.value

        if all([bauteil, dammdicke, taetigkeit, einheit, menge]):
            base_price = get_base_price(bauteil, dammdicke)
            material_price = get_material_price(bauteil, dammdicke)
            taetigkeit_faktor = get_taetigkeit_faktor(taetigkeit)
            
            price = (base_price + material_price) * taetigkeit_faktor * float(menge)
            self.preis_field.value = f"{price:.2f}"
        else:
            self.preis_field.value = ""
        
        self.update()

    def add_article(self, e):
        bauteil = self.bauteil_dropdown.value
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        einheit = self.einheit_dropdown.value
        menge = self.menge_field.value
        preis = self.preis_field.value

        if all([bauteil, dammdicke, taetigkeit, einheit, menge, preis]):
            position = get_positionsnummer(bauteil, dammdicke, taetigkeit)
            zwischensumme = float(preis) * float(menge)
            
            new_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(position)),
                    ft.DataCell(ft.Text(bauteil)),
                    ft.DataCell(ft.Text(dammdicke)),
                    ft.DataCell(ft.Text(taetigkeit)),
                    ft.DataCell(ft.Text(einheit)),
                    ft.DataCell(ft.Text(menge)),
                    ft.DataCell(ft.Text(preis)),
                    ft.DataCell(ft.Text(f"{zwischensumme:.2f}")),
                    ft.DataCell(
                        ft.IconButton(
                            ft.icons.DELETE,
                            on_click=lambda _: self.delete_article(new_row)
                        )
                    ),
                ]
            )
            
            self.article_list_header.rows.append(new_row)
            self.article_summaries.append({
                'zwischensumme': zwischensumme,
                'sonderleistungen': []
            })
            
            self.clear_input_fields()
            self.update_total_price()
            self.update()
        else:
            self.show_snack_bar("Bitte füllen Sie alle Felder aus")

    def delete_article(self, row):
        index = self.article_list_header.rows.index(row)
        self.article_list_header.rows.remove(row)
        del self.article_summaries[index]
        self.update_total_price()
        self.update()

    def clear_input_fields(self):
        self.bauteil_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.einheit_dropdown.value = None
        self.menge_field.value = ""
        self.preis_field.value = ""

    def update_total_price(self):
        total = sum(summary['zwischensumme'] for summary in self.article_summaries)
        for zuschlag in self.selected_zuschlaege:
            total *= (1 + zuschlag[1])
        self.total_price_text.value = f"Gesamtpreis: {total:.2f} €"
        self.update()

    def get_invoice_data(self):
        return {
            'client_name': self.invoice_detail_fields['client_name'].value,
            'bestell_nr': self.invoice_detail_fields['bestell_nr'].value,
            'bestelldatum': self.invoice_detail_fields['bestelldatum'].value,
            'baustelle': self.invoice_detail_fields['baustelle'].value,
            'anlagenteil': self.invoice_detail_fields['anlagenteil'].value,
            'aufmass_nr': self.invoice_detail_fields['aufmass_nr'].value,
            'auftrags_nr': self.invoice_detail_fields['auftrags_nr'].value,
            'ausfuehrungsbeginn': self.invoice_detail_fields['ausfuehrungsbeginn'].value,
            'ausfuehrungsende': self.invoice_detail_fields['ausfuehrungsende'].value,
            'articles': [
                {
                    'position': row.cells[0].content.value,
                    'bauteil': row.cells[1].content.value,
                    'dammdicke': row.cells[2].content.value,
                    'taetigkeit': row.cells[3].content.value,
                    'einheit': row.cells[4].content.value,
                    'menge': row.cells[5].content.value,
                    'preis': row.cells[6].content.value,
                    'zwischensumme': row.cells[7].content.value,
                }
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
            'sonderleistungen': self.selected_sonderleistungen,
            'total_price': float(self.total_price_text.value.split(":")[1].strip().replace("€", ""))
        }

    def save_invoice_to_db(self, invoice_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoice (
                    client_name, bestell_nr, bestelldatum, baustelle, anlagenteil,
                    aufmass_nr, auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende,
                    zuschlaege, total_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data['client_name'], invoice_data['bestell_nr'],
                invoice_data['bestelldatum'], invoice_data['baustelle'],
                invoice_data['anlagenteil'], invoice_data['aufmass_nr'],
                invoice_data['auftrags_nr'], invoice_data['ausfuehrungsbeginn'],
                invoice_data['ausfuehrungsende'],
                ','.join(f"{z[0]}:{z[1]}" for z in invoice_data['zuschlaege']),
                invoice_data['total_price']
            ))
            
            invoice_id = cursor.lastrowid
            
            for article in invoice_data['articles']:
                cursor.execute('''
                    INSERT INTO invoice_items (
                        invoice_id, position, bauteil, dammdicke, taetigkeit,
                        einheit, menge, preis, zwischensumme
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id, article['position'], article['bauteil'],
                    article['dammdicke'], article['taetigkeit'], article['einheit'],
                    article['menge'], article['preis'], article['zwischensumme']
                ))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_next_aufmass_nr(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_nr = cursor.fetchone()[0]
            return str(int(max_nr) + 1) if max_nr else "1"
        finally:
            cursor.close()
            conn.close()

    def show_dialog(self, dialog):
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def close_dialog(self):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def show_snack_bar(self, text):
        self.page.snack_bar = ft.SnackBar(ft.Text(text))
        self.page.snack_bar.open = True
        self.page.update()

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





    
    
