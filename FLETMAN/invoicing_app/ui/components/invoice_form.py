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

    def show_error(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.update()

    def update_dn_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        if bauteil in ["Bauteil", "Formteil", "Kleinkram"]:
            # Wenn eine Überschrift ausgewählt wurde, nichts tun
            return

        if self.is_rohrleitung_or_formteil(bauteil):
            self.dn_dropdown.visible = True
            self.da_dropdown.visible = True
            
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in all_dn_options]
            self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in all_da_options]
            
            # Setze die Werte auf None, um eine neue Auswahl zu erzwingen
            self.dn_dropdown.value = None
            self.da_dropdown.value = None
        else:
            self.dn_dropdown.visible = False
            self.da_dropdown.visible = False
            self.dn_dropdown.value = None
            self.da_dropdown.value = None

        self.update_dammdicke_options()
        self.update_field_visibility()
        self.update_price()
        self.update()

    def load_all_dn_da_options(self, bauteil):
        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                cursor.execute('SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DN IS NOT NULL ORDER BY DN', ('Rohrleitung',))
                all_dn_options = [int(float(dn[0])) for dn in cursor.fetchall()]
                
                cursor.execute('SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DA IS NOT NULL ORDER BY DA', ('Rohrleitung',))
                all_da_options = [float(da[0]) for da in cursor.fetchall()]
            else:
                all_dn_options = []
                all_da_options = []
            
            return all_dn_options, all_da_options
        finally:
            cursor.close()

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    # ... (andere Methoden)

    # ... (andere Methoden)

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

    def update_dammdicke_options(self, e=None):
        bauteil = self.artikelbeschreibung_dropdown.value
        if not bauteil:
            return

        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None

        dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        if dammdicke_options:
            self.dammdicke_dropdown.value = str(dammdicke_options[0])
        else:
            self.dammdicke_dropdown.value = None
        self.dammdicke_dropdown.update()

    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                if dn and da:
                    cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size IS NOT NULL ORDER BY Size', ('Rohrleitung', dn, da))
                elif dn:
                    cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND Size IS NOT NULL ORDER BY Size', ('Rohrleitung', dn))
                elif da:
                    cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DA = ? AND Size IS NOT NULL ORDER BY Size', ('Rohrleitung', da))
                else:
                    cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND Size IS NOT NULL ORDER BY Size', ('Rohrleitung',))
            else:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND Size IS NOT NULL ORDER BY Size', (bauteil,))
            
            sizes = [row[0] for row in cursor.fetchall()]
            return sorted(set(sizes), key=lambda x: float(x.split()[0]) if isinstance(x, str) and x.split()[0].replace('.', '').isdigit() else x)
        finally:
            cursor.close()

    def update_price(self, e=None):
        category = self.category_dropdown.value
        bauteil = self.artikelbeschreibung_dropdown.value
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
        if bauteil == 'Rohrleitung':
            return True
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
        return cursor.fetchone() is not None

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    def update_dn_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        if bauteil and self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            if dn:
                compatible_da = self.get_corresponding_da(bauteil, dn)
                new_da_value = str(compatible_da[0]) if compatible_da else None
                self.da_dropdown.value = new_da_value
                
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
                self.da_dropdown.value = new_da_value
            else:
                self.da_dropdown.value = None
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            self.da_dropdown.update()
        
        self.update_dammdicke_options()
        self.update_price()

    def update_dn_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            if dn:
                compatible_da = self.get_corresponding_da(bauteil, dn)
                new_da_value = str(compatible_da[0]) if compatible_da else None
                self.da_dropdown.value = new_da_value
                
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            else:
                self.da_dropdown.value = None
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            self.da_dropdown.update()
        
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def update_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        da = self.da_dropdown.value
        if self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            if da:
                compatible_dn = self.get_corresponding_dn(bauteil, da)
                new_dn_value = str(compatible_dn[0]) if compatible_dn else None
                self.dn_dropdown.value = new_dn_value
                
                self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            else:
                self.dn_dropdown.value = None
                self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            self.dn_dropdown.update()
        
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def get_corresponding_da(self, bauteil, dn):
        query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DN = ? AND DA IS NOT NULL ORDER BY DA'
        params = (bauteil, dn)
        options = self.get_from_cache_or_db(f"da_options_{bauteil}_{dn}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_dn(self, bauteil, da):
        query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DA = ? AND DN IS NOT NULL ORDER BY DN'
        params = (bauteil, da)
        options = self.get_from_cache_or_db(f"dn_options_{bauteil}_{da}", query, params)
        return [int(float(dn[0])) for dn in options]

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
        for field in self.invoice_detail_fields:
            options = self.get_from_cache_or_db(f"invoice_options_{field}", f"SELECT DISTINCT {field} FROM invoice WHERE {field} IS NOT NULL AND {field} != '' ORDER BY {field}")
            self.invoice_detail_fields[field].options = [ft.dropdown.Option(str(option[0])) for option in options]
            self.invoice_detail_fields[field].options.append(ft.dropdown.Option("Neuer Eintrag"))

    def toggle_new_entry(self, e, field):
        dropdown = self.invoice_detail_fields[field]
        text_field = self.new_entry_fields[field]
        text_field.visible = dropdown.value == "Neuer Eintrag"
        self.update()

    def build(self):
        invoice_details = ft.Column([
            ft.Row([
                ft.Column([
                    self.invoice_detail_fields[field],
                    self.new_entry_fields[field]
                ], expand=1)
                for field in ['client_name', 'bestell_nr', 'bestelldatum', 'baustelle', 'anlagenteil']
            ]),
            ft.Row([
                ft.Column([
                    self.invoice_detail_fields[field],
                    self.new_entry_fields[field]
                ], expand=1)
                for field in ['aufmass_nr', 'auftrags_nr', 'ausfuehrungsbeginn', 'ausfuehrungsende']
            ])
        ])

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
                self.price_field,
                self.quantity_input,
                self.zwischensumme_field,
                ft.ElevatedButton("Hinzufügen", on_click=self.add_article_row),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ])

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
                            invoice_details,
                            ft.Container(height=20),
                            ft.Text("Artikeleingabe:", weight=ft.FontWeight.BOLD),
                            artikel_eingabe,
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
        )

    def load_items(self, e=None):
        category = self.category_dropdown.value
        if not category:
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            if category == "Aufmaß":
                # Lade Bauteile aus der price_list Tabelle
                cursor.execute("SELECT DISTINCT Bauteil FROM price_list ORDER BY Bauteil")
                bauteile = [row[0] for row in cursor.fetchall()]

                # Lade Formteile aus der Faktoren Tabelle
                cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Formteil' ORDER BY Bezeichnung")
                formteile = [row[0] for row in cursor.fetchall()]

                # Gruppiere Kleinkram-Bauteile
                kleinkram_bauteile = ["Ausschnitte", "Rosetten", "Einsätze", "Blenden/Stirnscheiben", "Regenabweiser"]
                
                # Erstelle die Optionen mit Trennern für das Artikelbeschreibung-Dropdown
                options = [
                    ft.dropdown.Option("Bauteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(bauteil) for bauteil in bauteile if bauteil not in kleinkram_bauteile],
                    ft.dropdown.Option("Kleinkram", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(bauteil) for bauteil in kleinkram_bauteile],
                    ft.dropdown.Option("Formteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(formteil) for formteil in formteile]
                ]
                self.artikelbeschreibung_dropdown.options = options

                # Lade Tätigkeiten
                cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit' ORDER BY Bezeichnung")
                taetigkeiten = [row[0] for row in cursor.fetchall()]
                self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]

            elif category == "Material":
                cursor.execute("SELECT Positionsnummer, Benennung FROM Materialpreise ORDER BY Benennung")
                items = cursor.fetchall()
                self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(key=item[0], text=f"{item[0]} - {item[1]}") for item in items]
            elif category in ["Lohn", "Festpreis"]:
                # Implementieren Sie hier die Logik für Lohn und Festpreis, falls erforderlich
                pass

            self.update_field_visibility()
            self.update()

        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
        finally:
            cursor.close()
            conn.close()

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
        total_price = sum(float(article['zwischensumme'].replace(',', '.')) for article in self.article_summaries)
        self.total_price_field.value = f"Gesamtpreis: {total_price:.2f} €".replace('.', ',')
        self.update()

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

    def update_quantity(self, e):
        self.update_price()  # Aktualisiert die Zwischensumme
        self.update_total_price()  # Aktualisiert den Gesamtpreis

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
                # Implementieren Sie hier die Logik für andere Kategorien
                return None

            result = cursor.fetchone()
            return result[0] if result else None
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
                    cursor.execute('SELECT Value FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?', (bauteil, dn, da, dammdicke))
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

    def is_rohrleitung_or_formteil(self, bauteil):
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    # ... (andere Methoden)

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