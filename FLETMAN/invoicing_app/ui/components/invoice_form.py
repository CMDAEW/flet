import sqlite3
import flet as ft
from database.db_operations import get_db_connection
import asyncio
import re

class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.cache = {}  # Cache für Datenbankabfragen
        self.article_summaries = []  # Liste zur Speicherung der Zwischensummen
        
        # Initialisierung der Sonderleistungen und Zuschläge
        self.sonderleistungen = []
        self.selected_sonderleistungen = []
        self.zuschlaege = []
        self.selected_zuschlaege = []
        
        # Initialisieren Sie die Buttons mit on_click Handlern
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen)
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege)
        
        # Initialisieren Sie die Container für die Checkboxen
        self.sonderleistungen_container = ft.Column(visible=False)
        self.zuschlaege_container = ft.Column(visible=False)
        
        # Erstellen der UI-Elemente
        self.create_ui_elements()
        
        # Laden der Optionen
        self.load_invoice_options()
        self.load_sonderleistungen()
        self.load_zuschlaege()
        self.load_taetigkeiten()

    def create_ui_elements(self):
        # UI-Elemente erstellen
        self.total_price_field = ft.TextField(label="Gesamtpreis", read_only=True)
        self.article_list = ft.Column()
        self.article_rows = []
        
        # Dropdown-Menüs
        self.category_dropdown = ft.Dropdown(
            label="Kategorie",
            options=[
                ft.dropdown.Option("Aufmaß"),
                ft.dropdown.Option("Material"),
                ft.dropdown.Option("Lohn"),
                ft.dropdown.Option("Festpreis")
            ],
            on_change=self.load_items
        )
        self.artikelbeschreibung_dropdown = ft.Dropdown(label="Artikelbeschreibung", on_change=self.update_dn_da_fields, width=180)
        self.dn_dropdown = ft.Dropdown(label="DN", on_change=self.update_dn_fields, width=60)
        self.da_dropdown = ft.Dropdown(label="DA", on_change=self.update_da_fields, width=60)
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=self.update_price, width=90)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=self.update_price, width=180)
        
        # Textfelder
        self.position_field = ft.TextField(label="Position", read_only=True, width=80)
        self.price_field = ft.TextField(label="Preis", read_only=True, width=80)
        self.quantity_input = ft.TextField(label="Menge", value="1", on_change=self.update_price, width=70)
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True, width=120)

        # Snackbar für Benachrichtigungen
        self.snackbar = ft.SnackBar(content=ft.Text(""))

        # Rechnungsdetails Felder
        self.client_name_dropdown = ft.Dropdown(label="Kunde", on_change=lambda e: self.toggle_new_entry(e, "client_name"))
        self.bestell_nr_dropdown = ft.Dropdown(label="Bestell-Nr.", on_change=lambda e: self.toggle_new_entry(e, "bestell_nr"))
        self.bestelldatum_dropdown = ft.Dropdown(label="Bestelldatum", on_change=lambda e: self.toggle_new_entry(e, "bestelldatum"))
        self.baustelle_dropdown = ft.Dropdown(label="Baustelle", on_change=lambda e: self.toggle_new_entry(e, "baustelle"))
        self.anlagenteil_dropdown = ft.Dropdown(label="Anlagenteil", on_change=lambda e: self.toggle_new_entry(e, "anlagenteil"))
        self.aufmass_nr_dropdown = ft.Dropdown(label="Aufmaß-Nr.", on_change=lambda e: self.toggle_new_entry(e, "aufmass_nr"))
        self.auftrags_nr_dropdown = ft.Dropdown(label="Auftrags-Nr.", on_change=lambda e: self.toggle_new_entry(e, "auftrags_nr"))
        self.ausfuehrungsbeginn_dropdown = ft.Dropdown(label="Ausführungsbeginn", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsbeginn"))
        self.ausfuehrungsende_dropdown = ft.Dropdown(label="Ausführungsende", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsende"))

        # Neue Eintragsfelder für Rechnungsdetails
        self.client_name_new_entry = ft.TextField(label="Neuer Kunde", visible=False)
        self.bestell_nr_new_entry = ft.TextField(label="Neue Bestell-Nr.", visible=False)
        self.bestelldatum_new_entry = ft.TextField(label="Neues Bestelldatum", visible=False)
        self.baustelle_new_entry = ft.TextField(label="Neue Baustelle", visible=False)
        self.anlagenteil_new_entry = ft.TextField(label="Neues Anlagenteil", visible=False)
        self.aufmass_nr_new_entry = ft.TextField(label="Neue Aufmaß-Nr.", visible=False)
        self.auftrags_nr_new_entry = ft.TextField(label="Neue Auftrags-Nr.", visible=False)
        self.ausfuehrungsbeginn_new_entry = ft.TextField(label="Neuer Ausführungsbeginn", visible=False)
        self.ausfuehrungsende_new_entry = ft.TextField(label="Neues Ausführungsende", visible=False)

    def update_dammdicke_options(self, e=None):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        if bauteil and (not self.is_rohrleitung_or_formteil(bauteil) or (dn and da)):
            dammdicke_options = self.get_all_dammdicke_options(bauteil, dn, da)
            if dammdicke_options:
                self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
                self.dammdicke_dropdown.value = str(dammdicke_options[0])
                self.dammdicke_dropdown.visible = True
            else:
                self.dammdicke_dropdown.options = []
                self.dammdicke_dropdown.value = None
                self.dammdicke_dropdown.visible = False
        else:
            self.dammdicke_dropdown.options = []
            self.dammdicke_dropdown.value = None
            self.dammdicke_dropdown.visible = False
        
        self.dammdicke_dropdown.update()
        self.update_price()

    def update_dn_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        if bauteil and dn and self.is_rohrleitung_or_formteil(bauteil):
            da_options = self.get_corresponding_da(bauteil, dn)
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]
            if not self.da_dropdown.value or self.da_dropdown.value not in [str(da) for da in da_options]:
                self.da_dropdown.value = str(da_options[0]) if da_options else None
            self.da_dropdown.update()
        self.update_dammdicke_options()
        self.update_price()

    def update_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        da = self.da_dropdown.value
        if bauteil and da and self.is_rohrleitung_or_formteil(bauteil):
            dn_options = self.get_corresponding_dn(bauteil, da)
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in dn_options]
            if not self.dn_dropdown.value or self.dn_dropdown.value not in [str(dn) for dn in dn_options]:
                self.dn_dropdown.value = str(dn_options[0]) if dn_options else None
            self.dn_dropdown.update()
        self.update_dammdicke_options()
        self.update_price()

    def get_corresponding_da(self, bauteil, dn):
        query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DN = ? AND DA IS NOT NULL ORDER BY DA'
        params = ('Rohrleitung', dn)
        options = self.get_from_cache_or_db(f"da_options_{bauteil}_{dn}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_dn(self, bauteil, da):
        query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DA = ? AND DN IS NOT NULL ORDER BY DN'
        params = ('Rohrleitung', da)
        options = self.get_from_cache_or_db(f"dn_options_{bauteil}_{da}", query, params)
        return [float(dn[0]) for dn in options]

    def get_all_da_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DA IS NOT NULL ORDER BY DA'
            params = ('Rohrleitung',)
        else:
            return []
    
        options = self.get_from_cache_or_db(f"da_options_{bauteil}", query, params)
        return [float(da[0]) for da in options]

    def update_price(self, e=None):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value

        if not all([bauteil, dammdicke, taetigkeit]) or (self.is_rohrleitung_or_formteil(bauteil) and not all([dn, da])):
            self.price_field.value = ""
            self.zwischensumme_field.value = ""
            self.price_field.update()
            self.zwischensumme_field.update()
            return

        cursor = self.conn.cursor()
        if self.is_rohrleitung_or_formteil(bauteil):
            cursor.execute('''
                SELECT Value FROM price_list 
                WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?
            ''', ('Rohrleitung', dn, da, dammdicke))
        else:
            cursor.execute('''
                SELECT Value FROM price_list 
                WHERE Bauteil = ? AND Size = ?
            ''', (bauteil, dammdicke))
        
        result = cursor.fetchone()
        if result:
            base_price = float(result[0])
            
            # Tätigkeit-Faktor anwenden
            cursor.execute('SELECT Faktor FROM Taetigkeiten WHERE Taetigkeit = ?', (taetigkeit,))
            taetigkeit_result = cursor.fetchone()
            if taetigkeit_result:
                base_price *= float(taetigkeit_result[0])
            
            # Sonderleistungen-Faktoren anwenden
            for sonderleistung in self.selected_sonderleistungen:
                cursor.execute('SELECT Faktor FROM Sonderleistungen WHERE Sonderleistung = ?', (sonderleistung,))
                faktor_result = cursor.fetchone()
                if faktor_result:
                    base_price *= float(faktor_result[0])
            
            # Zuschläge-Faktoren anwenden
            for zuschlag in self.selected_zuschlaege:
                cursor.execute('SELECT Faktor FROM Zuschlaege WHERE Zuschlag = ?', (zuschlag,))
                faktor_result = cursor.fetchone()
                if faktor_result:
                    base_price *= float(faktor_result[0])
            
            self.price_field.value = f"{base_price:.2f}"
            quantity = float(self.quantity_input.value) if self.quantity_input.value else 1
            zwischensumme = base_price * quantity
            self.zwischensumme_field.value = f"{zwischensumme:.2f}"
        else:
            self.price_field.value = ""
            self.zwischensumme_field.value = ""

        self.price_field.update()
        self.zwischensumme_field.update()

    def update_selected_sonderleistungen(self, e):
        self.selected_sonderleistungen = [cb.label for cb in self.sonderleistungen_container.controls if cb.value]
        self.update_price()

    def update_selected_zuschlaege(self, e):
        self.selected_zuschlaege = [cb.label for cb in self.zuschlaege_container.controls if cb.value]
        self.update_price()

    def load_sonderleistungen(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT Sonderleistung FROM Sonderleistungen ORDER BY Sonderleistung")
        sonderleistungen = cursor.fetchall()
        self.sonderleistungen = [s[0] for s in sonderleistungen]
        self.sonderleistungen_container.controls.clear()
        for option in self.sonderleistungen:
            checkbox = ft.Checkbox(label=option, on_change=self.update_selected_sonderleistungen)
            self.sonderleistungen_container.controls.append(checkbox)

    def load_zuschlaege(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT Zuschlag FROM Zuschlaege ORDER BY Zuschlag")
        zuschlaege = cursor.fetchall()
        self.zuschlaege = [z[0] for z in zuschlaege]
        self.zuschlaege_container.controls.clear()
        for option in self.zuschlaege:
            checkbox = ft.Checkbox(label=option, on_change=self.update_selected_zuschlaege)
            self.zuschlaege_container.controls.append(checkbox)

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    # Verwenden Sie diese Methode in anderen Funktionen, z.B.:
    def get_all_dn_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DN IS NOT NULL ORDER BY DN'
            params = ('Rohrleitung',)
        else:
            return []
    
        options = self.get_from_cache_or_db(f"dn_options_{bauteil}", query, params)
        return [float(dn[0]) for dn in options]

    def show_snackbar(self, message):
        self.snackbar.content = ft.Text(message)
        self.snackbar.open = True
        self.update()

    def add_article_row(self, e):
        new_row = ft.Row([
            ft.Text(self.position_field.value),
            ft.Text(self.artikelbeschreibung_dropdown.value),
            ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else ""),
            ft.Text(self.da_dropdown.value if self.da_dropdown.visible else ""),
            ft.Text(self.dammdicke_dropdown.value),
            ft.Text(self.price_field.value),
            ft.Text(self.quantity_input.value),
            ft.Text(self.zwischensumme_field.value),
            ft.IconButton(
                icon=ft.icons.DELETE,
                on_click=lambda _: self.remove_article_row(new_row)
            )
        ])
        self.article_list.controls.append(new_row)
        self.add_zwischensumme(float(self.zwischensumme_field.value))
        self.reset_fields()
        self.update()

    def remove_article_row(self, row):
        index = self.article_list.controls.index(row)
        self.article_list.controls.remove(row)
        self.remove_zwischensumme(index)
        self.update()

    def create_article_row(self):
        # Create a new row with dropdowns and fields for article details
        position_field = ft.TextField(label="Position", read_only=True)
        artikelbeschreibung_dropdown = ft.Dropdown(label="Artikelbeschreibung", on_change=self.update_price)
        dn_dropdown = ft.Dropdown(label="DN", on_change=self.update_price)
        da_dropdown = ft.Dropdown(label="DA", on_change=self.update_price)
        dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=self.update_price)
        taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=self.update_price)
        price_field = ft.TextField(label="Preis", read_only=True)
        quantity_input = ft.TextField(label="Menge", value="1", on_change=self.update_price)
        zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True)

        # Create a responsive row for the article
        return ft.ResponsiveRow([
            ft.Column([position_field], col={"sm": 12, "md": 1}),
            ft.Column([artikelbeschreibung_dropdown], col={"sm": 12, "md": 2}),
            ft.Column([taetigkeit_dropdown], col={"sm": 12, "md": 2}),
            ft.Column([dn_dropdown], col={"sm": 12, "md": 1}),
            ft.Column([da_dropdown], col={"sm": 12, "md": 1}),
            ft.Column([dammdicke_dropdown], col={"sm": 12, "md": 1}),
            ft.Column([price_field], col={"sm": 12, "md": 1}),
            ft.Column([quantity_input], col={"sm": 12, "md": 1}),
            ft.Column([zwischensumme_field], col={"sm": 12, "md": 1}),
        ])

    def update_article_rows(self):
        # Update the article rows based on the current selections
        for row in self.article_rows:
            # Logic to update each row based on the current selections
            pass

    def load_taetigkeiten(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT Taetigkeit FROM Taetigkeiten ORDER BY Taetigkeit")
        taetigkeiten = cursor.fetchall()
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.value = None  # No preselection
        self.taetigkeit_dropdown.visible = True

    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        self.update()

    def toggle_zuschlaege(self, e):
        print("Zuschläge Button geklickt")
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.update()

    def build(self):
        # Load invoice options
        self.load_invoice_options()

        artikel_eingabe = ft.Column([
            ft.Row([
                self.position_field,
                self.taetigkeit_dropdown,
                self.artikelbeschreibung_dropdown,
                self.dn_dropdown,
                self.da_dropdown,
                self.dammdicke_dropdown,
                ft.Column([
                    self.sonderleistungen_button,
                    self.sonderleistungen_container
                ], width=130),
                ft.Column([
                    self.zuschlaege_button,
                    self.zuschlaege_container
                ], width=90),
                self.price_field,
                self.quantity_input,
                self.zwischensumme_field,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
        ])

        # Create a scrollable container using ListView
        return ft.Container(
            content=ft.ListView(
                controls=[
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=self.category_dropdown,
                                alignment=ft.alignment.center,
                                margin=ft.margin.only(bottom=20)
                            ),
                            # Invoice details section
                            ft.ResponsiveRow([
                                ft.Column([self.client_name_dropdown, self.client_name_new_entry], col={"sm": 12, "md": 4}),
                                ft.Column([self.bestell_nr_dropdown, self.bestell_nr_new_entry], col={"sm": 12, "md": 4}),
                                ft.Column([self.bestelldatum_dropdown, self.bestelldatum_new_entry], col={"sm": 12, "md": 4}),
                            ]),
                            ft.ResponsiveRow([
                                ft.Column([self.baustelle_dropdown, self.baustelle_new_entry], col={"sm": 12, "md": 4}),
                                ft.Column([self.anlagenteil_dropdown, self.anlagenteil_new_entry], col={"sm": 12, "md": 4}),
                                ft.Column([self.aufmass_nr_dropdown, self.aufmass_nr_new_entry], col={"sm": 12, "md": 4}),
                            ]),
                            ft.ResponsiveRow([
                                ft.Column([self.auftrags_nr_dropdown, self.auftrags_nr_new_entry], col={"sm": 12, "md": 4}),
                                ft.Column([self.ausfuehrungsbeginn_dropdown, self.ausfuehrungsbeginn_new_entry], col={"sm": 12, "md": 4}),
                                ft.Column([self.ausfuehrungsende_dropdown, self.ausfuehrungsende_new_entry], col={"sm": 12, "md": 4}),
                            ]),
                            ft.Container(height=20),  # Abstandhalter
                            ft.Text("Artikeleingabe:", weight=ft.FontWeight.BOLD),
                            artikel_eingabe,
                            ft.Container(height=20),  # Abstandhalter
                            ft.Text("Artikelliste:", weight=ft.FontWeight.BOLD),
                            self.article_list,
                            ft.Container(height=20),  # Abstandhalter
                            self.total_price_field,  # Gesamtpreisfeld
                        ]),
                        padding=10,
                    )
                ],
                expand=True,
                auto_scroll=True
            ),
            expand=True,
            height=600,  # Set a fixed height or use page.height to make it full height
        )

    def update_total_price(self):
        total_price = sum(self.article_summaries)  # Summe der aktuellen Zwischensummen
        self.total_price_field.value = f"{total_price:.2f}"  # Gesamtpreis aktualisieren
        self.total_price_field.update()  # Aktualisiere das Feld in der Benutzeroberfläche

    def update_dammdicke_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        if bauteil:
            dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
            self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
            self.dammdicke_dropdown.visible = True

        self.update_price()
        self.update()

    
    def update_dn_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        if bauteil:
            is_rohrleitung_or_formteil = self.is_rohrleitung_or_formteil(bauteil)
            
            self.dn_dropdown.visible = is_rohrleitung_or_formteil
            self.da_dropdown.visible = is_rohrleitung_or_formteil
            
        if is_rohrleitung_or_formteil:
            dn_options = self.get_all_dn_options(bauteil)
            da_options = self.get_all_da_options(bauteil)
            
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in dn_options]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]
            
            if not self.dn_dropdown.value or self.dn_dropdown.value not in [str(dn) for dn in dn_options]:
                self.dn_dropdown.value = str(dn_options[0]) if dn_options else None
            
            if not self.da_dropdown.value or self.da_dropdown.value not in [str(da) for da in da_options]:
                self.da_dropdown.value = str(da_options[0]) if da_options else None
            
            self.dn_dropdown.update()
            self.da_dropdown.update()
        else:
            self.dn_dropdown.options = []
            self.dn_dropdown.value = None
            self.da_dropdown.options = []
            self.da_dropdown.value = None
        
        self.update_dammdicke_options()
        self.update_price()
        
    
    
        self.dn_dropdown.update()
        self.da_dropdown.update()
        self.update()

    def get_all_dammdicke_options(self, bauteil, dn=None, da=None):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size IS NOT NULL'
            params = ('Rohrleitung', dn, da)
        else:
            query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND Size IS NOT NULL'
            params = (bauteil,)
        
        options = self.get_from_cache_or_db(f"dammdicke_options_{bauteil}_{dn}_{da}", query, params)
        
        # Sortiere die Optionen
        sorted_options = sorted(options, key=lambda x: self.parse_dammdicke(x[0]))
        return [size[0] for size in sorted_options]

    def parse_dammdicke(self, dammdicke_str):
        # Extrahiere die erste Zahl aus dem String
        match = re.search(r'\d+', dammdicke_str)
        if match:
            return int(match.group())
        return 0  # Fallback, falls keine Zahl gefunden wird

    def on_dammdicke_change(self, e):
        self.update_price()

    def is_rohrleitung_or_formteil(self, bauteil):
        if bauteil == 'Rohrleitung':
            return True
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
        return cursor.fetchone() is not None

    def load_items(self, e):
        selected_category = self.category_dropdown.value
        cursor = self.conn.cursor()

        # Reset all fields
        self.reset_fields()

        if selected_category == "Aufmaß":
            self.load_aufmass_options(cursor)
        elif selected_category in ["Material", "Lohn", "Festpreis"]:
            self.load_other_options(cursor, selected_category)

        # Adjust visibility of fields based on selections
        self.update_field_visibility()

        self.update()

    def update_field_visibility(self):
        # Hide or show DN and DA dropdowns based on the selected category
        if self.category_dropdown.value == "Aufmaß":
            self.dn_dropdown.visible = True
            self.da_dropdown.visible = True
        else:
            self.dn_dropdown.visible = False
            self.da_dropdown.visible = False

        # Update the layout to remove gaps
        self.dn_dropdown.update()
        self.da_dropdown.update()

        # Adjust the visibility of other fields to ensure no gaps
        if not self.dn_dropdown.visible and not self.da_dropdown.visible:
            self.dammdicke_dropdown.visible = True  # Ensure the next field is visible
        else:
            self.dammdicke_dropdown.visible = True  # Keep it visible if DN or DA is shown

        # Update the layout to remove gaps
        self.dammdicke_dropdown.update()
        self.position_field.update()
        self.price_field.update()
        self.quantity_input.update()
        self.zwischensumme_field.update()

    def reset_fields(self):
        for field in [self.position_field, self.price_field, self.zwischensumme_field]:
            field.value = ""
        for dropdown in [self.artikelbeschreibung_dropdown, self.taetigkeit_dropdown, self.dn_dropdown, self.da_dropdown, self.dammdicke_dropdown]:
            dropdown.options.clear()
            dropdown.visible = False
        self.quantity_input.visible = False
        
        # Zurücksetzen der Sonderleistungen und Zuschläge
        for checkbox in self.sonderleistungen_container.controls:
            checkbox.value = False
        for checkbox in self.zuschlaege_container.controls:
            checkbox.value = False
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        
        # Container ausblenden
        self.sonderleistungen_container.visible = False
        self.zuschlaege_container.visible = False


    def load_other_options(self, cursor, category):
        if category == "Material":
            cursor.execute("SELECT Positionsnummer, Benennung FROM Materialpreise")
        elif category == "Lohn":
            cursor.execute("SELECT Positionsnummer, Taetigkeit FROM Taetigkeiten")
        elif category == "Festpreis":
            cursor.execute("SELECT Positionsnummer, Formteilbezeichnung FROM Formteile")

        items = cursor.fetchall()
        self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(key=item[0], text=f"{item[0]} - {item[1]}") for item in items]
        self.artikelbeschreibung_dropdown.visible = True
        for field in [self.position_field, self.price_field, self.quantity_input, self.zwischensumme_field]:
            field.visible = True

    def add_item_to_invoice(self, e):
        # Extract selected values
        selected_item = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        size = self.dammdicke_dropdown.value if self.dammdicke_dropdown.visible else None
        taetigkeit = self.taetigkeit_dropdown.value
        position = self.position_field.value
        price = self.price_field.value
        quantity = self.quantity_input.value
        zwischensumme = self.zwischensumme_field.value

        # Add the item to the invoice table
        # Here you can implement how to store the invoice items
        # For example, you might want to append to a list or update a database

        # Display the added item in the UI (for example, in a list or table)
        print(f"Added item: Position: {position}, Price: {price}, Quantity: {quantity}, Zwischensumme: {zwischensumme}")

        # Clear the input fields after adding the item
        self.reset_item_fields()

        # Update the UI
        self.update()

    def reset_item_fields(self):
        self.artikelbeschreibung_dropdown.value = None
        self.dn_dropdown.value = None
        self.da_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.position_field.value = ""
        self.price_field.value = ""
        self.quantity_input.value = "1"
        self.zwischensumme_field.value = ""


    def toggle_new_entry(self, e, field):
        dropdown = getattr(self, f"{field}_dropdown")
        text_field = getattr(self, f"{field}_new_entry")
        text_field.visible = dropdown.value == "Neuer Eintrag"
        self.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()


    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                bauteil = 'Rohrleitung'

            if dn and da:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil, dn, da))
            elif dn:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil, dn))
            elif da:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DA = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil, da))
            else:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil,))

            sizes = [row[0] for row in cursor.fetchall() if row[0] is not None]
            return sorted(set(sizes), key=self.sort_dammdicke)
        finally:
            cursor.close()

    def sort_dammdicke(self, size):
        # If it's a range, take the first value
        if ' - ' in size:
            return int(size.split(' - ')[0])
        # If it's a single number, convert directly
        try:
            return int(size)
        except ValueError:
            # If not a number, return original string
            return size

    # Fügen Sie eine neue Methode hinzu, um eine Artikelzeile hinzuzufügen
    def add_article_row(self, e):
        # Logik zum Hinzufügen einer neuen Artikelzeile
        # Hier können Sie die Eingabefelder für die neue Zeile erstellen und zur UI hinzufügen
        pass

    # Fügen Sie eine Methode zum Entfernen der Zeile hinzu
    def remove_article_row(self, e):
        # Logik zum Entfernen der Artikelzeile
        pass

    def update_total_price(self):
        total_price = sum(self.article_summaries)  # Summe der aktuellen Zwischensummen
        self.total_price_field.value = f"{total_price:.2f}"  # Gesamtpreis aktualisieren
        self.total_price_field.update()  # Aktualisiere das Feld in der Benutzeroberfläche

    def update_zwischensumme(self, index, new_value):
        # Aktualisiere die Zwischensumme an der gegebenen Position
        self.article_summaries[index] = new_value
        self.update_total_price()  # Aktualisiere den Gesamtpreis
        self.reset_fields()  # Setze die Felder zurück nach jeder Änderung der Zwischensumme

    def add_zwischensumme(self, value):
        # Füge eine neue Zwischensumme hinzu
        self.article_summaries.append(value)
        self.update_total_price()  # Aktualisiere den Gesamtpreis

    def remove_zwischensumme(self, index):
        # Entferne eine Zwischensumme an der gegebenen Position
        del self.article_summaries[index]
        self.update_total_price()  # Aktualisiere den Gesamtpreis

    # Diese Methode sollte bei jeder Änderung der Menge aufgerufen werden
    def update_quantity(self, e):
        self.update_price()  # Aktualisiert die Zwischensumme
        self.update_total_price()  # Aktualisiert den Gesamtpreis
          
    def update_total_price(self):
        total_price = sum(self.article_summaries)  # Summe der aktuellen Zwischensummen
        self.total_price_field.value = f"{total_price:.2f}"  # Gesamtpreis aktualisieren
        self.total_price_field.update()  # Aktualisiere das Feld in der Benutzeroberfläche

    def load_dammdicke_options(self):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        if bauteil and dn and da:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT DISTINCT Size 
            FROM price_list 
            WHERE Bauteil = ? AND DN = ? AND DA = ? 
            ORDER BY Size
        ''', (bauteil, dn, da))
            dammdicke_options = cursor.fetchall()
            self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size[0])) for size in dammdicke_options]
            self.dammdicke_dropdown.value = None  # Setzen Sie den Wert zurück
            self.dammdicke_dropdown.visible = True
        else:
            self.dammdicke_dropdown.options = []
            self.dammdicke_dropdown.value = None
            self.dammdicke_dropdown.visible = False
            self.dammdicke_dropdown.update()

    def update_dammdicke_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        if bauteil:
            dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
            self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
            self.dammdicke_dropdown.visible = True

        self.update_price()
        self.update()

    def load_items(self, e):
        selected_category = self.category_dropdown.value
        cursor = self.conn.cursor()

        # Reset all fields
        self.reset_fields()

        if selected_category == "Aufmaß":
            self.load_aufmass_options(cursor)
        elif selected_category in ["Material", "Lohn", "Festpreis"]:
            self.load_other_options(cursor, selected_category)

        # Adjust visibility of fields based on selections
        self.update_field_visibility()

        self.update()

    def update_field_visibility(self):
        # Hide or show DN and DA dropdowns based on the selected category
        if self.category_dropdown.value == "Aufmaß":
            self.dn_dropdown.visible = False
            self.da_dropdown.visible = False
        else:
            self.dn_dropdown.visible = True
            self.da_dropdown.visible = True

        # Update the layout to remove gaps
        self.dn_dropdown.update()
        self.da_dropdown.update()

        # Adjust the visibility of other fields to ensure no gaps
        if not self.dn_dropdown.visible and not self.da_dropdown.visible:
            self.dammdicke_dropdown.visible = True  # Ensure the next field is visible
        else:
            self.dammdicke_dropdown.visible = True  # Keep it visible if DN or DA is shown

        # Update the layout to remove gaps
        self.dammdicke_dropdown.update()
        self.position_field.update()
        self.price_field.update()
        self.quantity_input.update()
        self.zwischensumme_field.update()

    def reset_fields(self):
        for field in [self.position_field, self.price_field, self.zwischensumme_field]:
            field.value = ""
        for dropdown in [self.artikelbeschreibung_dropdown, self.taetigkeit_dropdown, self.dn_dropdown, self.da_dropdown, self.dammdicke_dropdown]:
            dropdown.options.clear()
            dropdown.visible = False
        self.quantity_input.visible = False
        
        # Zurücksetzen der Sonderleistungen und Zuschläge
        for checkbox in self.sonderleistungen_container.controls:
            checkbox.value = False
        for checkbox in self.zuschlaege_container.controls:
            checkbox.value = False
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        
        # Container ausblenden
        self.sonderleistungen_container.visible = False
        self.zuschlaege_container.visible = False

    def load_aufmass_options(self, cursor):
        # Load Tätigkeiten
        cursor.execute("SELECT DISTINCT Taetigkeit FROM Taetigkeiten ORDER BY Taetigkeit")
        taetigkeiten = cursor.fetchall()
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.visible = True

        # Load Zuschläge
        cursor.execute("SELECT DISTINCT Zuschlag FROM Zuschlaege ORDER BY Zuschlag")
        zuschlaege = cursor.fetchall()
        self.zuschlaege_button.options = [ft.dropdown.Option(zuschlag[0]) for zuschlag in zuschlaege]
        self.zuschlaege_button.visible = True

        # Lade Bauteil (Artikelbeschreibung) und Formteile
        cursor.execute("SELECT DISTINCT Bauteil FROM price_list ORDER BY Bauteil")
        bauteile = cursor.fetchall()
        cursor.execute("SELECT DISTINCT Formteilbezeichnung FROM Formteile ORDER BY Formteilbezeichnung")
        formteile = cursor.fetchall()

        self.artikelbeschreibung_dropdown.options = [
            ft.dropdown.Option("Bauteile", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        ] + [
            ft.dropdown.Option(b[0]) for b in bauteile
        ] + [
            ft.dropdown.Option("Formteile", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        ] + [
            ft.dropdown.Option(f[0]) for f in formteile
        ]
        self.artikelbeschreibung_dropdown.visible = True

        # Make other fields visible
        for field in [self.dn_dropdown, self.da_dropdown, self.dammdicke_dropdown, self.position_field, self.price_field, self.quantity_input, self.zwischensumme_field]:
            field.visible = True

    def load_other_options(self, cursor, category):
        if category == "Material":
            cursor.execute("SELECT Positionsnummer, Benennung FROM Materialpreise")
        elif category == "Lohn":
            cursor.execute("SELECT Positionsnummer, Taetigkeit FROM Taetigkeiten")
        elif category == "Festpreis":
            cursor.execute("SELECT Positionsnummer, Formteilbezeichnung FROM Formteile")

        items = cursor.fetchall()
        self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(key=item[0], text=f"{item[0]} - {item[1]}") for item in items]
        self.artikelbeschreibung_dropdown.visible = True
        for field in [self.position_field, self.price_field, self.quantity_input, self.zwischensumme_field]:
            field.visible = True

    def add_item_to_invoice(self, e):
        # Extract selected values
        selected_item = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        size = self.dammdicke_dropdown.value if self.dammdicke_dropdown.visible else None
        taetigkeit = self.taetigkeit_dropdown.value
        position = self.position_field.value
        price = self.price_field.value
        quantity = self.quantity_input.value
        zwischensumme = self.zwischensumme_field.value

        # Add the item to the invoice table
        # Here you can implement how to store the invoice items
        # For example, you might want to append to a list or update a database

        # Display the added item in the UI (for example, in a list or table)
        print(f"Added item: Position: {position}, Price: {price}, Quantity: {quantity}, Zwischensumme: {zwischensumme}")

        # Clear the input fields after adding the item
        self.reset_item_fields()

        # Update the UI
        self.update()

    def reset_item_fields(self):
        self.artikelbeschreibung_dropdown.value = None
        self.dn_dropdown.value = None
        self.da_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.position_field.value = ""
        self.price_field.value = ""
        self.quantity_input.value = "1"
        self.zwischensumme_field.value = ""

    def load_invoice_options(self):
        cursor = self.conn.cursor()
        fields = [
            "client_name", "bestell_nr", "bestelldatum", "baustelle", "anlagenteil",
            "aufmass_nr", "auftrags_nr", "ausfuehrungsbeginn", "ausfuehrungsende"
        ]
        for field in fields:
            try:
                cursor.execute(f"SELECT DISTINCT {field} FROM invoice WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
                options = cursor.fetchall()
                dropdown = getattr(self, f"{field}_dropdown")
                dropdown.options = [ft.dropdown.Option(str(option[0])) for option in options]
                dropdown.options.append(ft.dropdown.Option("Neuer Eintrag"))
            except sqlite3.OperationalError as e:
                print(f"Error loading options for {field}: {e}")
                dropdown = getattr(self, f"{field}_dropdown")
                dropdown.options = [ft.dropdown.Option("Neuer Eintrag")]

    def toggle_new_entry(self, e, field):
        dropdown = getattr(self, f"{field}_dropdown")
        text_field = getattr(self, f"{field}_new_entry")
        text_field.visible = dropdown.value == "Neuer Eintrag"
        self.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        if bauteil == 'Rohrleitung':
            return True
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
        return cursor.fetchone() is not None

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                bauteil = 'Rohrleitung'

            if dn and da:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil, dn, da))
            elif dn:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil, dn))
            elif da:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DA = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil, da))
            else:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND value IS NOT NULL AND value != 0 ORDER BY Size', (bauteil,))

            sizes = [row[0] for row in cursor.fetchall() if row[0] is not None]
            return sorted(set(sizes), key=self.sort_dammdicke)
        finally:
            cursor.close()

    def sort_dammdicke(self, size):
        # If it's a range, take the first value
        if ' - ' in size:
            return int(size.split(' - ')[0])
        # If it's a single number, convert directly
        try:
            return int(size)
        except ValueError:
            # If not a number, return original string
            return size

    # Fügen Sie eine neue Methode hinzu, um eine Artikelzeile hinzuzufügen
    def add_article_row(self, e):
        # Logik zum Hinzufügen einer neuen Artikelzeile
        # Hier können Sie die Eingabefelder für die neue Zeile erstellen und zur UI hinzufügen
        pass

    # Fügen Sie eine Methode zum Entfernen der Zeile hinzu
def add_article_row(self, e):
    new_row = ft.Row([
        ft.Text(self.position_field.value, width=50),
        ft.Text(self.artikelbeschreibung_dropdown.value, expand=1),
        ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "", width=40),
        ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "", width=40),
        ft.Text(self.dammdicke_dropdown.value, width=70),
        ft.Text(self.taetigkeit_dropdown.value, width=100),
        ft.Text(self.price_field.value, width=70),
        ft.Text(self.quantity_input.value, width=50),
        ft.Text(self.zwischensumme_field.value, width=80),
        ft.IconButton(
            icon=ft.icons.DELETE,
            on_click=lambda _: self.remove_article_row(new_row)
        )
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    self.article_list.controls.append(new_row)
    self.add_zwischensumme(float(self.zwischensumme_field.value))
    self.reset_fields()
    self.update()

    def remove_article_row(self, row):
        index = self.article_list.controls.index(row)
        self.article_list.controls.remove(row)
        self.remove_zwischensumme(index)
        self.update()

    def update_total_price(self):
        total_price = sum(self.article_summaries)  # Summe der aktuellen Zwischensummen
        self.total_price_field.value = f"{total_price:.2f}"  # Gesamtpreis aktualisieren
        self.total_price_field.update()  # Aktualisiere das Feld in der Benutzeroberfläche

    def update_zwischensumme(self, index, new_value):
        # Aktualisiere die Zwischensumme an der gegebenen Position
        self.article_summaries[index] = new_value
        self.update_total_price()  # Aktualisiere den Gesamtpreis
        self.reset_fields()  # Setze die Felder zurück nach jeder Änderung der Zwischensumme

    def add_zwischensumme(self, value):
        # Füge eine neue Zwischensumme hinzu
        self.article_summaries.append(value)
        self.update_total_price()  # Aktualisiere den Gesamtpreis

    def remove_zwischensumme(self, index):
        # Entferne eine Zwischensumme an der gegebenen Position
        del self.article_summaries[index]
        self.update_total_price()  # Aktualisiere den Gesamtpreis

    # Diese Methode sollte bei jeder Änderung der Menge aufgerufen werden
    def update_quantity(self, e):
        self.update_price()  # Aktualisiert die Zwischensumme
        self.update_total_price()  # Aktualisiert den Gesamtpreis