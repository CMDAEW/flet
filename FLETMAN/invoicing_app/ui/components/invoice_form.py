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
        self.previous_bauteil = None

        self.create_ui_elements()
        self.load_data()

    def create_ui_elements(self):
        # Entfernen Sie den Aufmaß-Button
        # self.aufmass_button = ft.ElevatedButton("Aufmaß", on_click=self.on_aufmass_click, width=150)

        # Restlicher Code bleibt unverändert
        self.artikelbeschreibung_dropdown = ft.Dropdown(
            label="Artikelbeschreibung", 
            on_change=self.update_dn_da_fields, 
            width=250
        )
        self.dn_dropdown = ft.Dropdown(label="DN", width=100)
        self.da_dropdown = ft.Dropdown(label="DA", width=100)
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", width=150)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", width=200)  # Hier hinzugefügt

        # Textfelder
        self.position_field = ft.TextField(label="Position", read_only=True, width=100)
        self.price_field = ft.TextField(label="Preis", read_only=True, width=100)
        self.quantity_input = ft.TextField(label="Menge", value="1", on_change=self.update_price, width=90)
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True, width=140)
        self.total_price_field = ft.Text(value="Gesamtpreis: 0,00 €", style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD))

        # Buttons und Container
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen, width=180)
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege, width=180)
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
        self.load_aufmass_items()  # Laden Sie die Aufmaß-Items direkt

    def load_aufmass_items(self):
        cursor = self.conn.cursor()
        try:
            # Laden Sie Bauteile aus der Preisliste
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN Size LIKE '%-%' THEN 'Kleinkram'
                        ELSE 'Bauteile'
                    END AS Gruppe,
                    Bauteil
                FROM 
                    (SELECT DISTINCT Bauteil, Size FROM price_list)
                WHERE 
                    Bauteil != 'Rohrleitung'
            ''')
            
            grouped_items = {'Bauteile': set(), 'Formteile': set(), 'Kleinkram': set()}
            for gruppe, bauteil in cursor.fetchall():
                grouped_items[gruppe].add(bauteil)

            # Laden Sie Formteile aus der Faktoren-Tabelle
            cursor.execute('''
                SELECT Bezeichnung
                FROM Faktoren
                WHERE Art = 'Formteil'
            ''')
            formteile = cursor.fetchall()
            grouped_items['Formteile'] = set(item[0] for item in formteile)

            # Erstellen Sie die Optionen für das Dropdown
            options = [
                ft.dropdown.Option("Rohrleitung"),  # Rohrleitung als erste Option
                ft.dropdown.Option("Festpreis"),    # Festpreis als zweite Option
                ft.dropdown.Option("--- Bauteile ---", disabled=True)
            ]
            options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Bauteile'])])
            
            options.append(ft.dropdown.Option("--- Formteile ---", disabled=True))
            options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Formteile'])])
            
            options.append(ft.dropdown.Option("--- Kleinkram ---", disabled=True))
            options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Kleinkram'])])

            self.artikelbeschreibung_dropdown.options = options
            self.artikelbeschreibung_dropdown.value = None
            
            # Laden Sie die Tätigkeiten
            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung')
            taetigkeiten = [row[0] for row in cursor.fetchall()]
            self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]
            self.taetigkeit_dropdown.value = None
        finally:
            cursor.close()

        self.update()

    def build(self):
        # Gruppieren der Felder in drei Spalten
        field_columns = [
            ['client_name', 'bestell_nr', 'bestelldatum'],
            ['baustelle', 'anlagenteil', 'aufmass_nr'],
            ['auftrags_nr', 'ausfuehrungsbeginn', 'ausfuehrungsende']
        ]

        invoice_details = ft.Row([
            ft.Column([
                ft.Column([
                    self.invoice_detail_fields[field],
                    self.new_entry_fields[field]
                ])
                for field in column
            ], expand=1)
            for column in field_columns
        ])

        return ft.Container(
            content=ft.Column([
                # Entfernen Sie den Container mit dem Aufmaß-Button
                # Rest des Inhalts
                ft.Container(
                    content=ft.ListView(
                        controls=[
                            ft.Container(
                                content=ft.Column([
                                    invoice_details,
                                    ft.Container(height=20),
                                    ft.Text("Aufmaßeingabe:", weight=ft.FontWeight.BOLD),
                                    ft.Column([
                                        ft.Row([
                                            self.artikelbeschreibung_dropdown,
                                            self.dn_dropdown,
                                            self.da_dropdown,
                                            self.dammdicke_dropdown,
                                            self.taetigkeit_dropdown,
                                            ft.Column([
                                                self.sonderleistungen_button,
                                                self.sonderleistungen_container
                                            ], width=130),
                                            self.price_field,
                                            self.quantity_input,
                                            self.zwischensumme_field,
                                            ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
                                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    ]),
                                    ft.Container(height=20),
                                    ft.Text("Artikelliste:", weight=ft.FontWeight.BOLD),
                                    self.article_list,
                                    ft.Container(height=20),
                                    self.total_price_field,
                                    self.zuschlaege_button,
                                    self.zuschlaege_container,
                                ]),
                                padding=10,
                            )
                        ],
                        expand=True,
                        auto_scroll=True
                    ),
                    expand=True,
                ),
            ]),
            expand=True,
        )

    def update_field_visibility(self):
        is_festpreis = self.artikelbeschreibung_dropdown.value == "Festpreis"
        is_rohrleitung = self.artikelbeschreibung_dropdown.value == "Rohrleitung"
        
        self.dn_dropdown.visible = self.da_dropdown.visible = is_rohrleitung
        self.dammdicke_dropdown.visible = not is_festpreis
        self.taetigkeit_dropdown.visible = not is_festpreis
        
        self.artikelbeschreibung_dropdown.visible = True
        self.quantity_input.visible = True
        self.price_field.visible = True
        self.zwischensumme_field.visible = True
        
        # Wenn Festpreis ausgewählt ist, machen Sie das Preisfeld bearbeitbar
        self.price_field.read_only = not is_festpreis
        
        self.update()

    def update_dn_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        self.update_field_visibility()
        if self.is_rohrleitung_or_formteil(bauteil):
            self.auto_fill_rohrleitung_or_formteil(bauteil)
        else:
            self.dn_dropdown.value = None
            self.da_dropdown.value = None
        
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def show_error(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.update()

    def load_all_dn_da_options(self, bauteil):
        all_dn_options = self.get_all_dn_options(bauteil)
        all_da_options = self.get_all_da_options(bauteil)
        return all_dn_options, all_da_options

    def get_all_dn_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DN IS NOT NULL ORDER BY DN'
            params = ('Rohrleitung',)
        else:
            return []

        options = self.get_from_cache_or_db(f"dn_options_{bauteil}", query, params)
        return [int(float(dn[0])) for dn in options]

    def get_all_da_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DA IS NOT NULL ORDER BY DA'
            params = ('Rohrleitung',)
        else:
            return []
    
        options = self.get_from_cache_or_db(f"da_options_{bauteil}", query, params)
        return [float(da[0]) for da in options]

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    def update_dn_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
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
        self.update_price()
        self.update()

    def update_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
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
        self.update_price()
        self.update()

    def update_dn_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            self.auto_fill_rohrleitung_or_formteil(bauteil)
        else:
            self.dn_dropdown.visible = False
            self.da_dropdown.visible = False
            self.dn_dropdown.value = None
            self.da_dropdown.value = None
        
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def auto_fill_rohrleitung_or_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT DISTINCT DN
                FROM price_list
                WHERE Bauteil = 'Rohrleitung'
                ORDER BY DN
            ''')
            dn_options = [row[0] for row in cursor.fetchall()]
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in dn_options]
            self.dn_dropdown.value = None

            cursor.execute('''
                SELECT DISTINCT DA
                FROM price_list
                WHERE Bauteil = 'Rohrleitung'
                ORDER BY DA
            ''')
            da_options = [row[0] for row in cursor.fetchall()]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]
            self.da_dropdown.value = None
        finally:
            cursor.close()

    def update_dammdicke_options(self):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value

        if bauteil == "Festpreis":
            self.dammdicke_dropdown.options = []
            self.dammdicke_dropdown.value = None
            return

        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                query = '''
                    SELECT DISTINCT Size 
                    FROM price_list 
                    WHERE Bauteil = ? AND DN = ? AND DA = ?
                    ORDER BY CAST(SUBSTR(Size, 1, INSTR(Size, ' ') - 1) AS INTEGER)
                '''
                cursor.execute(query, ('Rohrleitung', dn, da))
            else:
                query = '''
                    SELECT DISTINCT Size 
                    FROM price_list 
                    WHERE Bauteil = ?
                    ORDER BY CAST(SUBSTR(Size, 1, INSTR(Size, ' ') - 1) AS INTEGER)
                '''
                cursor.execute(query, (bauteil,))

            dammdicken = [row[0] for row in cursor.fetchall()]
            self.dammdicke_dropdown.options = [ft.dropdown.Option(dammdicke) for dammdicke in dammdicken]
            
            if dammdicken:
                self.dammdicke_dropdown.value = dammdicken[0]
            else:
                self.dammdicke_dropdown.value = None
        finally:
            cursor.close()

        self.update()

    def update_price(self, e=None):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        quantity = self.quantity_input.value

        if not all([bauteil, quantity]):
            return

        try:
            quantity = float(quantity)
        except ValueError:
            self.show_error("Ungültige Menge")
            return

        if bauteil == "Festpreis":
            try:
                price = float(self.price_field.value)
            except ValueError:
                self.show_error("Ungültiger Preis")
                return
        else:
            cursor = self.conn.cursor()
            try:
                if self.is_rohrleitung_or_formteil(bauteil):
                    cursor.execute('''
                        SELECT Value
                        FROM price_list
                        WHERE Bauteil = 'Rohrleitung' AND DN = ? AND DA = ? AND Size = ?
                    ''', (dn, da, dammdicke))
                else:
                    cursor.execute('''
                        SELECT Value
                        FROM price_list
                        WHERE Bauteil = ? AND Size = ?
                    ''', (bauteil, dammdicke))
                
                result = cursor.fetchone()
                if result:
                    price = result[0]
                else:
                    self.show_error("Preis nicht gefunden")
                    return
            finally:
                cursor.close()

        # Anwenden von Faktoren (Tätigkeit, Sonderleistungen, Zuschläge)
        price = self.apply_factors(price, taetigkeit)

        total_price = price * quantity

        self.price_field.value = f"{price:.2f}"
        self.zwischensumme_field.value = f"{total_price:.2f}"
        
        self.update()

    def apply_factors(self, base_price, taetigkeit):
        cursor = self.conn.cursor()
        try:
            # Tätigkeit Faktor
            if taetigkeit:
                cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit,))
                result = cursor.fetchone()
                if result:
                    base_price *= result[0]

            # Sonderleistungen
            for sonderleistung, faktor in self.selected_sonderleistungen:
                base_price *= faktor

            # Zuschläge
            for zuschlag, faktor in self.selected_zuschlaege:
                base_price *= faktor

        finally:
            cursor.close()

        return base_price

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? ORDER BY Size'
                params = (dn, da)
            else:
                query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? ORDER BY Size'
                params = (bauteil,)
            
            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_corresponding_da(self, bauteil, dn):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DN = ? ORDER BY DA', (bauteil, dn))
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_corresponding_dn(self, bauteil, da):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DA = ? ORDER BY DN', (bauteil, da))
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_base_price(self, bauteil, dn, da, dammdicke):
        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                if self.is_formteil(bauteil):
                    cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
                    formteil_faktor = cursor.fetchone()
                    if formteil_faktor:
                        cursor.execute('SELECT Value FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? AND Size = ?', (dn, da, dammdicke))
                        base_price = cursor.fetchone()
                        if base_price:
                            return base_price[0] * formteil_faktor[0]
                else:
                    cursor.execute('SELECT Value FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? AND Size = ?', (dn, da, dammdicke))
                    result = cursor.fetchone()
                    if result:
                        return result[0]
            else:
                cursor.execute('SELECT Value FROM price_list WHERE Bauteil = ? AND Size = ?', (bauteil, dammdicke))
                result = cursor.fetchone()
                if result:
                    return result[0]
            return None
        finally:
            cursor.close()

    def get_material_price(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT Preis FROM Materialpreise WHERE Benennung = ?", (bauteil,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def get_taetigkeit_faktor(self, taetigkeit):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def get_positionsnummer(self, bauteil, dammdicke, dn=None, da=None, category="Aufmaß"):
        cursor = self.conn.cursor()
        try:
            if category == "Aufmaß":
                query = "SELECT Positionsnummer FROM price_list WHERE Bauteil = ? AND Size = ?"
                params = [bauteil, dammdicke]
                
                if self.is_rohrleitung_or_formteil(bauteil):
                    if dn is not None:
                        query += " AND DN = ?"
                        params.append(dn)
                    if da is not None:
                        query += " AND DA = ?"
                        params.append(da)
                
                cursor.execute(query + " LIMIT 1", params)
            elif category == "Material":
                cursor.execute("SELECT Positionsnummer FROM Materialpreise WHERE Benennung = ? LIMIT 1", (bauteil,))
            else:
                return None

            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def load_items(self, category):
        if category == "Aufmaß":
            self.load_aufmass_items()
        elif category == "Material":
            self.load_material_items()
        elif category == "Lohn":
            self.load_lohn_items()
        elif category == "Festpreis":
            self.load_festpreis_items()
        self.update_field_visibility()

    def load_material_items(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT Bauteil FROM price_list WHERE Category = "Material" ORDER BY Bauteil')
            items = [row[0] for row in cursor.fetchall()]
            self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(item) for item in items]
            self.artikelbeschreibung_dropdown.value = None
        finally:
            cursor.close()

    def load_lohn_items(self):
        # Implementieren Sie hier die Logik zum Laden der Lohn-Artikel
        pass

    def load_festpreis_items(self):
        # Implementieren Sie hier die Logik zum Laden der Festpreis-Artikel
        pass

    def load_invoice_options(self):
        for field_name in self.invoice_detail_fields:
            self.load_options_for_field(field_name)

    def load_options_for_field(self, field_name):
        cursor = self.conn.cursor()
        try:
            cursor.execute(f'SELECT DISTINCT {field_name} FROM invoice ORDER BY {field_name}')
            options = [row[0] for row in cursor.fetchall() if row[0]]
            self.invoice_detail_fields[field_name].options = [ft.dropdown.Option(option) for option in options]
            self.invoice_detail_fields[field_name].options.append(ft.dropdown.Option("Neuer Eintrag"))
        finally:
            cursor.close()

    def toggle_new_entry(self, e, field_name):
        if e.control.value == "Neuer Eintrag":
            self.new_entry_fields[field_name].visible = True
        else:
            self.new_entry_fields[field_name].visible = False
        self.update()

    def add_article_row(self, e):
        new_row = ft.Row([
            ft.Text(self.position_field.value, width=70),
            ft.Text(self.artikelbeschreibung_dropdown.value, expand=1),
            ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "", width=50),
            ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "", width=50),
            ft.Text(self.dammdicke_dropdown.value, width=90),
            ft.Text(self.taetigkeit_dropdown.value, width=120),
            ft.Text(self.price_field.value, width=90),
            ft.Text(self.quantity_input.value, width=70),
            ft.Text(self.zwischensumme_field.value, width=100),
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
        total_price = sum(float(article['zwischensumme'].replace(',', '.')) for article in self.article_summaries)
        self.total_price_field.value = f"Gesamtpreis: {total_price:.2f} €".replace('.', ',')
        self.update()

    def update_zwischensumme(self, index, new_value):
        self.article_summaries[index] = new_value
        self.update_total_price()
        self.reset_fields()

    def add_zwischensumme(self, value):
        self.article_summaries.append(value)
        self.update_total_price()

    def remove_zwischensumme(self, index):
        del self.article_summaries[index]
        self.update_total_price()

    def update_quantity(self, e):
        self.update_price()
        self.update_total_price()

    def reset_fields(self):
        self.artikelbeschreibung_dropdown.value = None
        self.dn_dropdown.value = None
        self.da_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.position_field.value = ""
        self.price_field.value = ""
        self.quantity_input.value = "1"
        self.zwischensumme_field.value = ""
        self.update()

    def get_invoice_data(self):
        invoice_data = {
            'client_name': self.invoice_detail_fields['client_name'].value,
            'bestell_nr': self.invoice_detail_fields['bestell_nr'].value,
            'bestelldatum': self.invoice_detail_fields['bestelldatum'].value,
            'baustelle': self.invoice_detail_fields['baustelle'].value,
            'anlagenteil': self.invoice_detail_fields['anlagenteil'].value,
            'aufmass_nr': self.invoice_detail_fields['aufmass_nr'].value,
            'auftrags_nr': self.invoice_detail_fields['auftrags_nr'].value,
            'ausfuehrungsbeginn': self.invoice_detail_fields['ausfuehrungsbeginn'].value,
            'ausfuehrungsende': self.invoice_detail_fields['ausfuehrungsende'].value,
            'category': self.current_category,
            'articles': []
        }

        for row in self.article_list.controls:
            article = {
                'position': row.controls[0].value,
                'artikelbeschreibung': row.controls[1].value,
                'dn': row.controls[2].value,
                'da': row.controls[3].value,
                'dammdicke': row.controls[4].value,
                'taetigkeit': row.controls[5].value,
                'price': row.controls[6].value,
                'quantity': row.controls[7].value,
                'zwischensumme': row.controls[8].value
            }
            invoice_data['articles'].append(article)

        invoice_data['total_price'] = self.total_price_field.value

        return invoice_data

    def load_invoice_data(self, invoice_data):
        for field, value in invoice_data.items():
            if field in self.invoice_detail_fields:
                self.invoice_detail_fields[field].value = value

        self.article_list.controls.clear()
        self.article_summaries.clear()

        for article in invoice_data['articles']:
            new_row = ft.Row([
                ft.Text(article['position'], width=70),
                ft.Text(article['artikelbeschreibung'], expand=1),
                ft.Text(article['dn'], width=50),
                ft.Text(article['da'], width=50),
                ft.Text(article['dammdicke'], width=90),
                ft.Text(article['taetigkeit'], width=120),
                ft.Text(article['price'], width=90),
                ft.Text(article['quantity'], width=70),
                ft.Text(article['zwischensumme'], width=100),
                ft.IconButton(
                    icon=ft.icons.DELETE,
                    on_click=lambda _: self.remove_article_row(new_row)
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            self.article_list.controls.append(new_row)
            self.add_zwischensumme(float(article['zwischensumme'].replace(',', '.')))

        self.total_price_field.value = invoice_data['total_price']
        self.update()


    def update_artikelbeschreibung_dropdown(self, bauteile):
        self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(bauteil) for bauteil in bauteile]
        self.artikelbeschreibung_dropdown.value = None
        self.artikelbeschreibung_dropdown.update()

    def load_all_bauteile(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                SELECT DISTINCT Bauteil 
                FROM (
                    SELECT Bezeichnung AS Bauteil FROM Faktoren WHERE Art = "Formteil"
                    UNION ALL
                    SELECT Bauteil FROM price_list WHERE Kategorie IN ("Kleinkram", "Bauteil")
                ) 
                ORDER BY Bauteil
            ''')
            bauteile = [row[0] for row in cursor.fetchall()]
            self.update_artikelbeschreibung_dropdown(bauteile)
        finally:
            cursor.close()

    # Fügen Sie diese Methoden hinzu:
    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        self.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.update()

    def load_faktoren(self, art):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
            faktoren = cursor.fetchall()
            container = self.sonderleistungen_container if art == "Sonderleistung" else self.zuschlaege_container
            for bezeichnung, faktor in faktoren:
                checkbox = ft.Checkbox(label=f"{bezeichnung} ({faktor})", value=False)
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.on_faktor_change(e, b, f, art)
                container.controls.append(checkbox)
        finally:
            cursor.close()

    def on_faktor_change(self, e, bezeichnung, faktor, art):
        if e.control.value:
            if art == "Sonderleistung":
                self.selected_sonderleistungen.append((bezeichnung, faktor))
            else:
                self.selected_zuschlaege.append((bezeichnung, faktor))
        else:
            if art == "Sonderleistung":
                self.selected_sonderleistungen = [x for x in self.selected_sonderleistungen if x[0] != bezeichnung]
            else:
                self.selected_zuschlaege = [x for x in self.selected_zuschlaege if x[0] != bezeichnung]
        self.update_price()