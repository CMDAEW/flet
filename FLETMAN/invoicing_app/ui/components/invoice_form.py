import logging
import sqlite3
import flet as ft
import re

from database.db_operations import get_db_connection
class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.cache = {}
        self.article_summaries = []
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        
        self.create_ui_elements()
        self.load_data()
        self.update_field_visibility()

    def create_ui_elements(self):
        # Dropdown-Menüs
        self.category_dropdown = ft.Dropdown(label="Kategorie", options=self.get_category_options(), on_change=self.load_items)
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
        self.total_price_field = ft.Text(value="Gesamtpreis: 0,00 €", style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD))

        # Buttons und Container
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen)
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege)
        self.sonderleistungen_container = ft.Column(visible=False, spacing=10)
        self.zuschlaege_container = ft.Column(visible=False, spacing=10)

        # Rechnungsdetails Felder
        self.invoice_detail_fields = {
            'client_name': ft.Dropdown(label="Kunde", on_change=lambda e: self.toggle_new_entry(e, "client_name")),
            'bestell_nr': ft.Dropdown(label="Bestell-Nr.", on_change=lambda e: self.toggle_new_entry(e, "bestell_nr")),
            'bestelldatum': ft.Dropdown(label="Bestelldatum", on_change=lambda e: self.toggle_new_entry(e, "bestelldatum")),
            'baustelle': ft.Dropdown(label="Baustelle", on_change=lambda e: self.toggle_new_entry(e, "baustelle")),
            'anlagenteil': ft.Dropdown(label="Anlagenteil", on_change=lambda e: self.toggle_new_entry(e, "anlagenteil")),
            'aufmass_nr': ft.Dropdown(label="Aufmaß-Nr.", on_change=lambda e: self.toggle_new_entry(e, "aufmass_nr")),
            'auftrags_nr': ft.Dropdown(label="Auftrags-Nr.", on_change=lambda e: self.toggle_new_entry(e, "auftrags_nr")),
            'ausfuehrungsbeginn': ft.Dropdown(label="Ausführungsbeginn", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsbeginn")),
            'ausfuehrungsende': ft.Dropdown(label="Ausführungsende", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsende")),
        }
        self.new_entry_fields = {key: ft.TextField(label=f"Neuer {value.label}", visible=False) for key, value in self.invoice_detail_fields.items()}

        self.article_list = ft.Column()

    def load_data(self):
        self.load_faktoren("Sonstige Zuschläge")
        self.load_faktoren("Sonderleistung")
        self.load_invoice_options()
        self.load_taetigkeiten()

    def get_category_options(self):
        return [ft.dropdown.Option(cat) for cat in ["Aufmaß", "Material", "Lohn", "Festpreis"]]

    def load_faktoren(self, art):
        faktoren = self.get_from_cache_or_db(f"faktoren_{art}", 'SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        container = self.sonderleistungen_container if art == "Sonderleistung" else self.zuschlaege_container
        container.controls.clear()
        for bezeichnung, faktor in faktoren:
            checkbox = ft.Checkbox(label=f"{bezeichnung} (Faktor: {faktor})", value=False)
            checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_faktoren(e, b, f, art)
            container.controls.append(checkbox)
        self.update()

    def update_selected_faktoren(self, e, bezeichnung, faktor, art):
        selected_list = self.selected_sonderleistungen if art == "Sonderleistung" else self.selected_zuschlaege
        if e.control.value:
            selected_list.append((bezeichnung, faktor))
        else:
            selected_list = [item for item in selected_list if item[0] != bezeichnung]
        self.update_price()

    def toggle_container(self, container):
        container.visible = not container.visible
        self.update()

    def toggle_sonderleistungen(self, e):
        self.toggle_container(self.sonderleistungen_container)

    def toggle_zuschlaege(self, e):
        self.toggle_container(self.zuschlaege_container)

    def load_items(self, e=None):
        category = self.category_dropdown.value
        if not category:
            return

        if category == "Aufmaß":
            self.load_aufmass_items()
        else:
            self.load_other_items(category)

    def load_aufmass_items(self):
        bauteile = self.get_from_cache_or_db("bauteile", "SELECT DISTINCT Bauteil FROM price_list ORDER BY Bauteil")
        formteile = self.get_from_cache_or_db("formteile", "SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Formteil' ORDER BY Bezeichnung")
        kleinkram_bauteile = ["Ausschnitte", "Rosetten", "Einsätze", "Blenden/Stirnscheiben", "Rosenabweiser"]
        
        options = [
            ft.dropdown.Option("Bauteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
            *[ft.dropdown.Option(bauteil[0]) for bauteil in bauteile if bauteil[0] not in kleinkram_bauteile],
            ft.dropdown.Option("Kleinkram", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
            *[ft.dropdown.Option(bauteil) for bauteil in kleinkram_bauteile],
            ft.dropdown.Option("Formteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
            *[ft.dropdown.Option(formteil[0]) for formteil in formteile]
        ]
        self.artikelbeschreibung_dropdown.options = options
        self.load_taetigkeiten()

    def load_other_items(self, category):
        items = self.get_from_cache_or_db(f"items_{category}", f"SELECT DISTINCT Bezeichnung FROM {category} ORDER BY Bezeichnung")
        self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(item[0]) for item in items]

    def load_taetigkeiten(self):
        taetigkeiten = self.get_from_cache_or_db("taetigkeiten", "SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit' ORDER BY Bezeichnung")
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]

    def update_dn_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            self.dn_dropdown.visible = self.da_dropdown.visible = True
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in all_dn_options]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in all_da_options]
            self.dn_dropdown.value = self.da_dropdown.value = None
        else:
            self.dn_dropdown.visible = self.da_dropdown.visible = False
            self.dn_dropdown.value = self.da_dropdown.value = None
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def update_dn_fields(self, e):
        self.update_corresponding_field('dn', 'da')

    def update_da_fields(self, e):
        self.update_corresponding_field('da', 'dn')

    def update_corresponding_field(self, source_field, target_field):
        bauteil = self.artikelbeschreibung_dropdown.value
        source_value = getattr(self, f"{source_field}_dropdown").value
        if bauteil and self.is_rohrleitung_or_formteil(bauteil) and source_value:
            corresponding_values = self.get_corresponding_values(bauteil, source_field, source_value)
            target_dropdown = getattr(self, f"{target_field}_dropdown")
            target_dropdown.value = str(corresponding_values[0])
            target_dropdown.options = [ft.dropdown.Option(str(value)) for value in corresponding_values]
            target_dropdown.update()
        self.update_dammdicke_options()
        self.update_price()

    def get_corresponding_values(self, bauteil, field, value):
        query = f'SELECT DISTINCT {field.upper()} FROM price_list WHERE Bauteil = ? AND {field.upper()} = ? AND {field.upper()} IS NOT NULL ORDER BY {field.upper()}'
        params = ('Rohrleitung', value)
        options = self.get_from_cache_or_db(f"{field}_options_{bauteil}_{value}", query, params)
        return [float(option[0]) if field == 'da' else int(float(option[0])) for option in options]

    def update_price(self, e=None):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        quantity = self.quantity_input.value

        if not all([bauteil, taetigkeit, quantity, dammdicke]):
            return

        try:
            quantity = float(quantity)
        except ValueError:
            self.show_error("Ungültige Menge")
            return

        base_price = self.get_base_price(bauteil, dn, da, dammdicke)
        if base_price is None:
            self.show_error("Kein Preis gefunden")
            return

        taetigkeit_faktor = self.get_taetigkeit_faktor(taetigkeit)
        if taetigkeit_faktor is None:
            self.show_error("Kein Tätigkeitsfaktor gefunden")
            return

        price = base_price * taetigkeit_faktor

        for _, faktor in self.selected_sonderleistungen + self.selected_zuschlaege:
            price *= faktor

        total_price = price * quantity

        self.price_field.value = f"{price:.2f}"
        self.zwischensumme_field.value = f"{total_price:.2f}"
        self.update()

    def get_base_price(self, bauteil, dn, da, dammdicke):
        if self.is_rohrleitung_or_formteil(bauteil):
            if self.is_formteil(bauteil):
                formteil_faktor = self.get_from_cache_or_db(f"formteil_faktor_{bauteil}", 'SELECT Faktor FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
                if formteil_faktor:
                    base_price = self.get_from_cache_or_db(f"base_price_rohrleitung_{dn}_{da}_{dammdicke}", 'SELECT Value FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? AND Size = ?', (dn, da, dammdicke))
                    if base_price:
                        return base_price[0][0] * formteil_faktor[0][0]
            else:
                base_price = self.get_from_cache_or_db(f"base_price_{bauteil}_{dn}_{da}_{dammdicke}", 'SELECT Value FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?', (bauteil, dn, da, dammdicke))
                if base_price:
                    return base_price[0][0]
        else:
            base_price = self.get_from_cache_or_db(f"base_price_{bauteil}_{dammdicke}", 'SELECT Value FROM price_list WHERE Bauteil = ? AND Size = ?', (bauteil, dammdicke))
            if base_price:
                return base_price[0][0]
        return None

    def get_taetigkeit_faktor(self, taetigkeit):
        faktor = self.get_from_cache_or_db(f"taetigkeit_faktor_{taetigkeit}", 'SELECT Faktor FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit,))
        return faktor[0][0] if faktor else None

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        formteil = self.get_from_cache_or_db(f"is_formteil_{bauteil}", 'SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil        return bool(formteil)

    def get_from_cache_or_db(self, key, query, params=()):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    def update_field_visibility(self):
        category = self.category_dropdown.value
        is_aufmass = category == "Aufmaß"
        
        self.dn_dropdown.visible = self.da_dropdown.visible = is_aufmass
        self.dammdicke_dropdown.visible = is_aufmass
        self.taetigkeit_dropdown.visible = is_aufmass
        
        self.artikelbeschreibung_dropdown.visible = True
        self.quantity_input.visible = True
        self.price_field.visible = True
        self.zwischensumme_field.visible = True
        
        self.update()

    def load_invoice_options(self):
        for field, dropdown in self.invoice_detail_fields.items():
            options = self.get_from_cache_or_db(f"invoice_options_{field}", f"SELECT DISTINCT {field} FROM invoice WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
            dropdown.options = [ft.dropdown.Option(str(option[0])) for option in options]
            dropdown.options.append(ft.dropdown.Option("Neuer Eintrag"))

    def toggle_new_entry(self, e, field):
        dropdown = self.invoice_detail_fields[field]
        text_field = self.new_entry_fields[field]
        text_field.visible = dropdown.value == "Neuer Eintrag"
        self.update()

    def load_all_dn_da_options(self, bauteil):
        all_dn_options = self.get_from_cache_or_db(f"all_dn_options_{bauteil}", 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DN IS NOT NULL ORDER BY DN', (bauteil,))
        all_da_options = self.get_from_cache_or_db(f"all_da_options_{bauteil}", 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DA IS NOT NULL ORDER BY DA', (bauteil,))
        return [dn[0] for dn in all_dn_options], [da[0] for da in all_da_options]

    def update_dammdicke_options(self):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        if bauteil:
            dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
            self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
            self.dammdicke_dropdown.value = None
        self.update()

    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = ?'
        params = [bauteil]
        if self.is_rohrleitung_or_formteil(bauteil):
            if dn:
                query += ' AND DN = ?'
                params.append(dn)
            if da:
                query += ' AND DA = ?'
                params.append(da)
        query += ' AND Size IS NOT NULL ORDER BY Size'
        options = self.get_from_cache_or_db(f"dammdicke_options_{bauteil}_{dn}_{da}", query, tuple(params))
        return [size[0] for size in options]

    def show_error(self, message):
        print(f"Error: {message}")
        # Hier können Sie eine Methode implementieren, um den Fehler in der UI anzuzeigen

    def build(self):
        return ft.Column([
            ft.Row([field for field in self.invoice_detail_fields.values()]),
            ft.Row([field for field in self.new_entry_fields.values()]),
            self.category_dropdown,
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
                ]),
                self.price_field,
                self.quantity_input,
                self.zwischensumme_field,
                ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
            ]),
            self.article_list,
            self.total_price_field,
            self.zuschlaege_button,
            self.zuschlaege_container,
        ])

    def add_article_row(self, e):
        # Implementieren Sie hier die Logik zum Hinzufügen einer neuen Artikelzeile
        pass