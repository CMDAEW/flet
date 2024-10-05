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
        self.current_category = None
        
        self.create_ui_elements()
        self.load_data()

    def create_ui_elements(self):
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
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=self.update_price, width=120)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=self.update_price, width=300)
        
        # Textfelder
        self.position_field = ft.TextField(label="Position", read_only=True, width=100)
        self.price_field = ft.TextField(label="Preis", read_only=True, width=100)
        self.quantity_input = ft.TextField(label="Menge", value="1", on_change=self.update_price, width=90)
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True, width=140)
        self.total_price_field = ft.Text(value="Gesamtpreis: 0,00 €", style=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD))

        # Buttons und Container
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen, width=200)
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

        # Spaltennamen für die Artikelliste mit dynamischer Breite
        self.article_list_header = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Position", size=20, weight=ft.FontWeight.BOLD), width=80),
                ft.DataColumn(ft.Text("Bauteil", size=20, weight=ft.FontWeight.BOLD), expand=3),
                ft.DataColumn(ft.Text("DN", size=20, weight=ft.FontWeight.BOLD), width=60),
                ft.DataColumn(ft.Text("DA", size=20, weight=ft.FontWeight.BOLD), width=60),
                ft.DataColumn(ft.Text("Dämmdicke", size=20, weight=ft.FontWeight.BOLD), expand=1),
                ft.DataColumn(ft.Text("Tätigkeit", size=20, weight=ft.FontWeight.BOLD), expand=2),
                ft.DataColumn(ft.Text("Einheit", size=20, weight=ft.FontWeight.BOLD), width=80),
                ft.DataColumn(ft.Text("Preis", size=20, weight=ft.FontWeight.BOLD), expand=1),
                ft.DataColumn(ft.Text("Menge", size=20, weight=ft.FontWeight.BOLD), width=80),
                ft.DataColumn(ft.Text("Zwischensumme", size=20, weight=ft.FontWeight.BOLD), expand=1),
                ft.DataColumn(ft.Text("Sonderleistungen", size=20, weight=ft.FontWeight.BOLD), expand=2),
                ft.DataColumn(ft.Text("Aktionen", size=20, weight=ft.FontWeight.BOLD), width=100),
            ],
            expand=True,
            horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
            vertical_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
        )

        self.einheit_field = ft.TextField(label="Einheit", read_only=True, width=80)

    def load_aufmass_items(self):
        cursor = self.conn.cursor()
        try:
            # Laden Sie alle Bauteile und gruppieren Sie sie
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN Bauteil IN (SELECT Bezeichnung FROM Faktoren WHERE Art = "Formteil") THEN 'Formteile'
                        WHEN Kategorie = "Kleinkram" THEN 'Kleinkram'
                        ELSE 'Bauteile'
                    END AS Gruppe,
                    Bauteil
                FROM price_list
                WHERE Bauteil != 'Rohrleitung'
                UNION
                SELECT 'Bauteile' AS Gruppe, 'Rohrleitung' AS Bauteil
                ORDER BY Gruppe, Bauteil
            ''')
            
            grouped_items = {}
            for gruppe, bauteil in cursor.fetchall():
                if gruppe not in grouped_items:
                    grouped_items[gruppe] = []
                grouped_items[gruppe].append(bauteil)

            # Erstellen Sie die Optionen für das Dropdown
            options = []
            for gruppe, bauteile in grouped_items.items():
                options.append(ft.dropdown.Option(gruppe, disabled=True))
                options.extend([ft.dropdown.Option(bauteil) for bauteil in bauteile])

            self.bauteil_dropdown.options = options
            self.bauteil_dropdown.value = None
            
            # Laden Sie die Tätigkeiten
            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung')
            taetigkeiten = [row[0] for row in cursor.fetchall()]
            self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]
            self.taetigkeit_dropdown.value = None
        finally:
            cursor.close()

        self.update()

    def on_category_click(self, e):
        # Setze alle Buttons zurück
        for button in self.category_buttons:
            button.style = None

        # Hebe den geklickten Button hervor
        e.control.style = ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE)

        # Aktualisiere die aktuelle Kategorie
        self.current_category = e.control.data

        # Führe die load_items Funktion aus
        self.load_items(self.current_category)

        self.update_field_visibility()  # Rufe update_field_visibility hier auf
        self.update()

    def load_items(self, category):
        # Ändern Sie diese Methode, um direkt die Kategorie zu akzeptieren
        if category == "Aufmaß":
            self.load_aufmass_items()
        elif category == "Material":
            self.load_material_items()
        elif category == "Lohn":
            self.load_lohn_items()
        elif category == "Festpreis":
            self.load_festpreis_items()
        self.update_field_visibility()

    def load_data(self):
        self.load_faktoren("Sonstige Zuschläge")
        self.load_faktoren("Sonderleistung")
        self.load_zuschlaege()
        self.load_invoice_options()

    def get_category_options(self):
        return [ft.dropdown.Option(cat) for cat in ["Aufmaß", "Material", "Lohn", "Festpreis"]]

    def load_faktoren(self, art):
        faktoren = self.get_from_cache_or_db(f"faktoren_{art}", 'SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        container = self.sonderleistungen_container if art == "Sonderleistung" else self.zuschlaege_container
        container.controls.clear()
        for bezeichnung, faktor in faktoren:
            checkbox = ft.Checkbox(label=f"{bezeichnung}", value=False)
            checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_faktoren(e, b, f, art)
            container.controls.append(checkbox)
        self.update()

    def update_selected_faktoren(self, e, bezeichnung, faktor, art):
        selected_list = self.selected_sonderleistungen if art == "Sonderleistung" else self.selected_zuschlaege
        if e.control.value:
            selected_list.append((bezeichnung, faktor))
        else:
            selected_list = [item for item in selected_list if item[0] != bezeichnung]
        
        if art == "Sonderleistung":
            self.selected_sonderleistungen = selected_list
        else:
            self.selected_zuschlaege = selected_list
        
        self.update_price()

    def toggle_container(self, container):
        container.visible = not container.visible
        self.update()

    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        self.zuschlaege_container.visible = False  # Schließe den anderen Container
        self.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        self.sonderleistungen_container.visible = False  # Schließe den anderen Container
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
        self.update_price()
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
        self.update_price()
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
        self.update_price()
        self.update()

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
            self.update_price()
        finally:
            cursor.close()


    def update_dammdicke_options(self, e=None):
        bauteil = self.bauteil_dropdown.value
        if not bauteil:
            return

        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None

        dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        if dammdicke_options:
            self.dammdicke_dropdown.value = str(dammdicke_options[0])  # Wählt die kleinste Dämmdicke als Standard
        else:
            self.dammdicke_dropdown.value = None
        self.dammdicke_dropdown.update()

    def update_price(self, e=None):
        category = self.current_category
        bauteil = self.bauteil_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        quantity = self.quantity_input.value

        if not all([category, bauteil, quantity]):
            return

        try:
            quantity = float(quantity)
        except ValueError:
            self.show_error("Ungültige Menge")
            return

        # Hole die Positionsnummer
        positionsnummer = self.get_positionsnummer(bauteil, dammdicke, dn, da, category)
        if positionsnummer:
            self.position_field.value = str(positionsnummer)
        else:
            self.position_field.value = ""

        if category == "Aufmaß":
            if not all([taetigkeit, dammdicke]):
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

            # Anwenden von Sonderleistungen
            for _, faktor in self.selected_sonderleistungen:
                price *= faktor

            # Anwenden von Zuschlägen
            for _, faktor in self.selected_zuschlaege:
                price *= faktor

        elif category == "Material":
            price = self.get_material_price(bauteil)
            if price is None:
                self.show_error("Kein Materialpreis gefunden")
                return

        else:
            # Für andere Kategorien (z.B. Lohn, Festpreis) müssen Sie hier die entsprechende Logik implementieren
            self.show_error("Preisberechnung für diese Kategorie nicht implementiert")
            return

        total_price = price * quantity

        self.price_field.value = f"{price:.2f}"
        self.zwischensumme_field.value = f"{total_price:.2f}"
        
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
    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? ORDER BY CAST(Size AS FLOAT)'
                params = (dn, da)
            else:
                query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? ORDER BY CAST(Size AS FLOAT)'
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
                ft.dropdown.Option("--- Bauteile ---", disabled=True)
            ]
            options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Bauteile'])])
            
            options.append(ft.dropdown.Option("--- Formteile ---", disabled=True))
            options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Formteile'])])
            
            options.append(ft.dropdown.Option("--- Kleinkram ---", disabled=True))
            options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Kleinkram'])])

            self.bauteil_dropdown.options = options
            self.bauteil_dropdown.value = None
            
            # Laden Sie die Tätigkeiten
            cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung')
            taetigkeiten = [row[0] for row in cursor.fetchall()]
            self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]
            self.taetigkeit_dropdown.value = None
        finally:
            cursor.close()

        self.update()

    def load_material_items(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT DISTINCT Bauteil FROM price_list WHERE Category = "Material" ORDER BY Bauteil')
            items = [row[0] for row in cursor.fetchall()]
            self.bauteil_dropdown.options = [ft.dropdown.Option(item) for item in items]
            self.bauteil_dropdown.value = None
        finally:
            cursor.close()

    def load_lohn_items(self):
        # Implementieren Sie hier die Logik zum Laden der Lohn-Artikel
        pass

    def load_festpreis_items(self):
        # Implementieren Sie hier die Logik zum Laden der Festpreis-Artikel
        pass

    def update_field_visibility(self):
        # Anstatt den Wert aus dem Dropdown zu holen, verwenden wir eine neue Variable
        category = self.current_category  # Diese Variable müssen wir in der Klasse definieren und in on_category_click aktualisieren
        is_aufmass = category == "Aufmaß"
        
        self.dn_dropdown.visible = self.da_dropdown.visible = is_aufmass
        self.dammdicke_dropdown.visible = is_aufmass
        self.taetigkeit_dropdown.visible = is_aufmass
        
        self.bauteil_dropdown.visible = True
        self.quantity_input.visible = True
        self.price_field.visible = True
        self.zwischensumme_field.visible = True
        
        self.update()

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
                ft.Row([self.delete_invoice_button], alignment=ft.MainAxisAlignment.END),
                self.category_row,  # Kategorie-Buttons (Aufmaß, Material, Lohn, Festpreis)
                ft.Container(height=20),
                invoice_details,  # Kopfdaten
                ft.Container(height=20),
                ft.Row([
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
                    self.sonderleistungen_button,
                    self.zuschlaege_button,
                    ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
                ], alignment=ft.MainAxisAlignment.START),
                self.sonderleistungen_container,
                self.zuschlaege_container,
                ft.Container(height=20),
                self.article_list_header,
                self.total_price_field,
                ft.Container(height=20),
                ft.Row([
                    ft.Column([
                        self.bemerkung_field,
                    ], expand=1),
                    ft.Column([
                        self.create_pdf_with_prices_button,
                        ft.Container(height=10),
                        self.create_pdf_without_prices_button,
                        ft.Container(height=10),
                        self.back_to_main_menu_button,
                    ], expand=1),
                ]),
            ]),
            padding=40,
            expand=True,
        )

    def add_article_row(self, e):
        new_row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(self.position_field.value, size=20)),
                ft.DataCell(ft.Text(self.bauteil_dropdown.value, size=20)),
                ft.DataCell(ft.Text(self.dn_dropdown.value if self.dn_dropdown.visible else "", size=20)),
                ft.DataCell(ft.Text(self.da_dropdown.value if self.da_dropdown.visible else "", size=20)),
                ft.DataCell(ft.Text(self.dammdicke_dropdown.value, size=20)),
                ft.DataCell(ft.Text(self.taetigkeit_dropdown.value, size=20)),
                ft.DataCell(ft.Text(self.einheit_field.value, size=20)),
                ft.DataCell(ft.Text(self.price_field.value, size=20)),
                ft.DataCell(ft.Text(self.quantity_input.value, size=20)),
                ft.DataCell(ft.Text(self.zwischensumme_field.value, size=20)),
                ft.DataCell(ft.Text(", ".join([sl[0] for sl in self.selected_sonderleistungen]), size=20)),
                ft.DataCell(ft.Row([
                    ft.IconButton(icon=ft.icons.EDIT, on_click=lambda _: self.edit_article_row(new_row)),
                    ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _: self.remove_article_row(new_row))
                ])),
            ]
        )
        self.article_list_header.rows.append(new_row)
        
        # Füge ein Dictionary zur article_summaries Liste hinzu
        self.article_summaries.append({
            'zwischensumme': float(self.zwischensumme_field.value.replace(',', '.')),
            'sonderleistungen': self.selected_sonderleistungen.copy()
        })
        
        self.update_total_price()
        self.reset_fields()
        self.update()

    def edit_article_row(self, row):
        # Implementieren Sie hier die Logik zum Bearbeiten einer Zeile
        self.position_field.value = row.cells[0].content.value
        self.bauteil_dropdown.value = row.cells[1].content.value
        self.dn_dropdown.value = row.cells[2].content.value
        self.da_dropdown.value = row.cells[3].content.value
        self.dammdicke_dropdown.value = row.cells[4].content.value
        self.taetigkeit_dropdown.value = row.cells[5].content.value
        self.einheit_field.value = row.cells[6].content.value
        self.price_field.value = row.cells[7].content.value
        self.quantity_input.value = row.cells[8].content.value
        self.zwischensumme_field.value = row.cells[9].content.value
        
        # Setze die Sonderleistungen zurück
        for checkbox in self.sonderleistungen_container.controls:
            checkbox.value = checkbox.label in row.cells[10].content.value.split(", ")
        
        self.update()

    def remove_article_row(self, row):
        index = self.article_list_header.rows.index(row)
        self.article_list_header.rows.remove(row)
        del self.article_summaries[index]
        self.update_total_price()
        self.update()

    def update_total_price(self):
        base_total_price = sum(article['zwischensumme'] for article in self.article_summaries)
        
        # Anwenden von Zuschlägen auf den Gesamtpreis
        for _, faktor in self.selected_zuschlaege:
            base_total_price *= faktor

        self.total_price_field.value = f"Gesamtpreis: {base_total_price:.2f} €".replace('.', ',')
        self.update()

    def reset_fields(self):
        self.bauteil_dropdown.value = None
        self.dn_dropdown.value = None
        self.da_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.position_field.value = ""
        self.price_field.value = ""
        self.quantity_input.value = "1"
        self.zwischensumme_field.value = ""
        
        # Setze auch die Sonderleistungen und Zuschläge zurück
        for checkbox in self.sonderleistungen_container.controls:
            checkbox.value = False
        for checkbox in self.zuschlaege_container.controls:
            checkbox.value = False
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        
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

        for row in self.article_list_header.rows:
            article = {
                'position': row.cells[0].content.value,
                'artikelbeschreibung': row.cells[1].content.value,
                'dn': row.cells[2].content.value,
                'da': row.cells[3].content.value,
                'dammdicke': row.cells[4].content.value,
                'taetigkeit': row.cells[5].content.value,
                'price': row.cells[6].content.value,
                'quantity': row.cells[7].content.value,
                'zwischensumme': row.cells[8].content.value
            }
            invoice_data['articles'].append(article)

        invoice_data['total_price'] = self.total_price_field.value

        return invoice_data

    def load_invoice_data(self, invoice_data):
        for field, value in invoice_data.items():
            if field in self.invoice_detail_fields:
                self.invoice_detail_fields[field].value = value

        self.article_list_header.rows.clear()
        self.article_summaries.clear()

        for article in invoice_data['articles']:
            new_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(article['position'])),
                    ft.DataCell(ft.Text(article['artikelbeschreibung'])),
                    ft.DataCell(ft.Text(article['dn'])),
                    ft.DataCell(ft.Text(article['da'])),
                    ft.DataCell(ft.Text(article['dammdicke'])),
                    ft.DataCell(ft.Text(article['taetigkeit'])),
                    ft.DataCell(ft.Text(article['price'])),
                    ft.DataCell(ft.Text(article['quantity'])),
                    ft.DataCell(ft.Text(article['zwischensumme'])),
                    ft.DataCell(ft.Text(", ".join([sl[0] for sl in self.selected_sonderleistungen]))),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.icons.EDIT, on_click=lambda _: self.edit_article_row(new_row)),
                        ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _: self.remove_article_row(new_row))
                    ])),
                ]
            )
            self.article_list_header.rows.append(new_row)
            self.add_zwischensumme(float(article['zwischensumme'].replace(',', '.')))

        self.total_price_field.value = invoice_data['total_price']
        self.update()


    def update_artikelbeschreibung_dropdown(self, bauteile):
        self.bauteil_dropdown.options = [ft.dropdown.Option(bauteil) for bauteil in bauteile]
        self.bauteil_dropdown.value = None
        self.bauteil_dropdown.update()

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

    def delete_invoice(self, e):
        # Implementieren Sie hier die Logik zum Löschen der gesamten Rechnung
        pass

    def create_pdf_with_prices(self, e):
        # Implementieren Sie hier die Logik zum Erstellen eines PDFs mit Preisen
        pass

    def create_pdf_without_prices(self, e):
        # Implementieren Sie hier die Logik zum Erstellen eines PDFs ohne Preise
        pass

    def back_to_main_menu(self, e):
        # Implementieren Sie hier die Logik zur Rückkehr zum Hauptmenü
        pass

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

    def update_einheit(self):
        bauteil = self.bauteil_dropdown.value
        if bauteil:
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