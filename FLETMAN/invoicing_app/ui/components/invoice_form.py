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
        
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen)
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege)
        
        self.sonderleistungen_container = ft.Column(visible=False, spacing=10)
        self.zuschlaege_container = ft.Column(visible=False, spacing=10)
        
        print("Initialisierung der InvoiceForm-Klasse abgeschlossen")
        
        self.load_faktoren("Sonstige Zuschläge")
        self.load_faktoren("Sonderleistung")
        
        self.create_ui_elements()
        
        self.load_invoice_options()
        self.load_taetigkeiten()
        self.update_field_visibility()
        self.update()

    def load_faktoren(self, art):
        cursor = self.conn.cursor()
        cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        faktoren = cursor.fetchall()
        
        container = self.sonderleistungen_container if art == "Sonderleistung" else self.zuschlaege_container
        container.controls.clear()
        
        print(f"Loading {art}: {faktoren}")  # Debug-Ausgabe
    
        for bezeichnung, faktor in faktoren:
            checkbox = ft.Checkbox(label=f"{bezeichnung} (Faktor: {faktor})", value=False)
            if art == "Sonderleistung":
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_sonderleistungen(e, b, f)
            else:
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_zuschlaege(e, b, f)
            container.controls.append(checkbox)
        
        print(f"Anzahl der geladenen {art}: {len(container.controls)}")
        
        self.update()

    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        print(f"Sonderleistungen Container Visibility: {self.sonderleistungen_container.visible}")  # Debug-Ausgabe
        print(f"Sonderleistungen Container Controls: {self.sonderleistungen_container.controls}")  # Debug-Ausgabe
        self.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        print(f"Zuschläge Container Visibility: {self.zuschlaege_container.visible}")  # Debug-Ausgabe
        print(f"Zuschläge Container Controls: {self.zuschlaege_container.controls}")  # Debug-Ausgabe
        self.update()

    def get_sonderleistungen(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT bezeichnung FROM faktoren WHERE art = 'sonderleistung'")
        sonderleistungen = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sonderleistungen

    def create_checkbox_container(self, title, items):
        if not items:
            return ft.Text(f"Keine {title} verfügbar")

        checkboxes = [ft.Checkbox(label=item, value=False) for item in items]
        return ft.Container(
            content=ft.Column([
                ft.Text(title, weight=ft.FontWeight.BOLD),
                ft.Row(controls=checkboxes)
            ])
        )

    def create_checkbox_container(self, title, items):
        if not items:
            return ft.Text(f"Keine {title} verfügbar")

        checkboxes = [ft.Checkbox(label=item, value=False) for item in items]
        return ft.Container(
            content=ft.Column([
                ft.Text(title, weight=ft.FontWeight.BOLD),
                ft.Row(controls=checkboxes)
            ])
        )

    def load_faktoren(self, art):
        cursor = self.conn.cursor()
        cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        faktoren = cursor.fetchall()
        
        container = self.sonderleistungen_container if art == "Sonderleistung" else self.zuschlaege_container
        container.controls.clear()
        
        print(f"Loading {art}: {faktoren}")  # Debug-Ausgabe
    
        for bezeichnung, faktor in faktoren:
            checkbox = ft.Checkbox(label=f"{bezeichnung} (Faktor: {faktor})", value=False)
            if art == "Sonderleistung":
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_sonderleistungen(e, b, f)
            else:
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_zuschlaege(e, b, f)
            container.controls.append(checkbox)
        
        # Debug-Ausgabe hinzufügen
        print(f"Anzahl der geladenen {art}: {len(container.controls)}")
        
        self.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        print(f"Zuschläge Container Visibility: {self.zuschlaege_container.visible}")  # Debug-Ausgabe
        print(f"Zuschläge Container Controls: {self.zuschlaege_container.controls}")  # Debug-Ausgabe
        self.update()

    def update_selected_sonderleistungen(self, e, bezeichnung, faktor):
        if e.control.value:
            self.selected_sonderleistungen.append((bezeichnung, faktor))
        else:
            self.selected_sonderleistungen = [s for s in self.selected_sonderleistungen if s[0] != bezeichnung]
        self.update_price()

    def update_selected_zuschlaege(self, e, bezeichnung, faktor):
        if e.control.value:
            self.selected_zuschlaege.append((bezeichnung, faktor))
        else:
            self.selected_zuschlaege = [z for z in self.selected_zuschlaege if z[0] != bezeichnung]
        self.update_price()

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
        self.dn_dropdown = ft.Dropdown(label="DN", on_change=self.update_dn_fields, width=60, options=[])
        self.da_dropdown = ft.Dropdown(label="DA", on_change=self.update_da_fields, width=60, options=[])
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

        # Sonderleistungen und Zuschläge
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.toggle_sonderleistungen)
        self.zuschlaege_button = ft.ElevatedButton("Zuschläge", on_click=self.toggle_zuschlaege)
        
        self.sonderleistungen_container = ft.Column(visible=False)
        self.zuschlaege_container = ft.Column(visible=False)

    def update_dammdicke_options(self, e=None):
        bauteil = self.artikelbeschreibung_dropdown.value
        if not bauteil:
            return

        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None

        dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        self.dammdicke_dropdown.value = None
        self.update()

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

    def update_dn_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        if bauteil in ["Bauteil", "Formteil"]:
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
        self.update_price()
        self.update()

    def update_dn_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        if bauteil and self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            if dn:
                compatible_da = self.get_corresponding_da(bauteil, dn)
                new_da_value = str(compatible_da[0])
                self.da_dropdown.value = new_da_value
                
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
                self.da_dropdown.value = new_da_value
            else:
                self.da_dropdown.value = None
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            self.da_dropdown.update()
        
        self.update_dammdicke_options()
        self.update_price()

    def update_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        da = self.da_dropdown.value
        print(f"Updating DA fields. Bauteil: {bauteil}, DA: {da}")  # Debug-Ausgabe
        if bauteil and self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            print(f"All DN options: {all_dn_options}")  # Debug-Ausgabe
            print(f"All DA options: {all_da_options}")  # Debug-Ausgabe
            
            self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            if da:
                compatible_dn = self.get_corresponding_dn(bauteil, da)
                print(f"Compatible DN for DA {da}: {compatible_dn}")  # Debug-Ausgabe
                new_dn_value = str(compatible_dn[0])
                print(f"Setting new DN value: {new_dn_value}")  # Debug-Ausgabe
                self.dn_dropdown.value = new_dn_value
                
                self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
                self.dn_dropdown.value = new_dn_value
            else:
                self.dn_dropdown.value = None
                self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            print(f"Final DN value: {self.dn_dropdown.value}")  # Debug-Ausgabe
            self.dn_dropdown.update()
        
        self.update_dammdicke_options()
        self.update_price()
        self.page.update()  # Aktualisiere die gesamte Seite

    def get_corresponding_da(self, bauteil, dn):
        query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DN = ? AND DA IS NOT NULL ORDER BY DA'
        params = ('Rohrleitung', dn)
        options = self.get_from_cache_or_db(f"da_options_{bauteil}_{dn}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_dn(self, bauteil, da):
        query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DA = ? AND DN IS NOT NULL ORDER BY DN'
        params = ('Rohrleitung', da)
        options = self.get_from_cache_or_db(f"dn_options_{bauteil}_{da}", query, params)
        result = [int(float(dn[0])) for dn in options]
        print(f"get_corresponding_dn result for DA {da}: {result}")  # Debug-Ausgabe
        return result

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

        # Anwenden von Sonderleistungen
        for _, faktor in self.selected_sonderleistungen:
            price *= faktor

        # Anwenden von Zuschlägen
        for _, faktor in self.selected_zuschlaege:
            price *= faktor

        total_price = price * quantity

        self.price_field.value = f"{price:.2f}"
        self.zwischensumme_field.value = f"{total_price:.2f}"
        self.update()

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
                # Für andere Bauteile, die weder Rohrleitung noch Formteil sind
                cursor.execute('SELECT Value FROM price_list WHERE Bauteil = ? AND Size = ?', (bauteil, dammdicke))
                result = cursor.fetchone()
                if result:
                    return result[0]
            return None
        finally:
            cursor.close()

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

        # Anwenden von Sonderleistungen
        for _, faktor in self.selected_sonderleistungen:
            price *= faktor

        # Anwenden von Zuschlägen
        for _, faktor in self.selected_zuschlaege:
            price *= faktor

        total_price = price * quantity

        self.price_field.value = f"{price:.2f}"
        self.zwischensumme_field.value = f"{total_price:.2f}"
        self.update()

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
                # Für andere Bauteile, die weder Rohrleitung noch Formteil sind
                cursor.execute('SELECT Value FROM price_list WHERE Bauteil = ? AND Size = ?', (bauteil, dammdicke))
                result = cursor.fetchone()
                if result:
                    return result[0]
            return None
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

    def show_error(self, message):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.update()

    def update_selected_sonderleistungen(self, e, bezeichnung):
        if e.control.value:
            self.selected_sonderleistungen.append(bezeichnung)
        else:
            self.selected_sonderleistungen.remove(bezeichnung)
        self.update_price()

    def update_selected_zuschlaege(self, e):
        self.selected_zuschlaege = [cb.label for cb in self.zuschlaege_container.controls if cb.value]
        self.update_price()

    def load_sonderleistungen(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = 'Sonderleistung' ORDER BY Bezeichnung")
        sonderleistungen = cursor.fetchall()
        self.sonderleistungen_container.controls.clear()
        for bezeichnung, faktor in sonderleistungen:
            checkbox = ft.Checkbox(
                label=f"{bezeichnung} (Faktor: {faktor})",
                on_change=lambda e, b=bezeichnung: self.update_selected_sonderleistungen(e, b)
            )
            self.sonderleistungen_container.controls.append(checkbox)

    def load_zuschlaege(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = 'Sonstige Zuschläge' ORDER BY Bezeichnung")
        zuschlaege = cursor.fetchall()
        self.zuschlaege = [(z[0], z[1]) for z in zuschlaege]
        self.zuschlaege_container.controls.clear()
        for bezeichnung, faktor in self.zuschlaege:
            checkbox = ft.Checkbox(label=f"{bezeichnung} (Faktor: {faktor})", on_change=self.update_selected_zuschlaege)
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
        return [int(float(dn[0])) for dn in options]  # Konvertiere zu Integer

    def show_snackbar(self, message):
        self.snackbar.content = ft.Text(message)
        self.snackbar.open = True
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
        cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit' ORDER BY Bezeichnung")
        taetigkeiten = cursor.fetchall()
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.value = None  # Keine Vorauswahl
        self.taetigkeit_dropdown.visible = True

    def toggle_sonderleistungen(self, e):
        self.sonderleistungen_container.visible = not self.sonderleistungen_container.visible
        print(f"Sonderleistungen Container Visibility: {self.sonderleistungen_container.visible}")  # Debug-Ausgabe
        self.update()

    def toggle_zuschlaege(self, e):
        self.zuschlaege_container.visible = not self.zuschlaege_container.visible
        print(f"Zuschläge Container Visibility: {self.zuschlaege_container.visible}")  # Debug-Ausgabe
        print(f"Zuschläge Container Controls: {self.zuschlaege_container.controls}")  # Debug-Ausgabe
        self.update()

    def update_selected_sonderleistungen(self, e, bezeichnung, faktor):
        if e.control.value:
            self.selected_sonderleistungen.append((bezeichnung, faktor))
        else:
            self.selected_sonderleistungen = [s for s in self.selected_sonderleistungen if s[0] != bezeichnung]
        self.update_price()

    def update_selected_zuschlaege(self, e, bezeichnung, faktor):
        if e.control.value:
            self.selected_zuschlaege.append((bezeichnung, faktor))
        else:
            self.selected_zuschlaege = [z for z in self.selected_zuschlaege if z[0] != bezeichnung]
        self.update_price()

    def build(self):
        # Debug-Ausgabe hinzufügen
        print("Build-Methode wird aufgerufen")
        
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
        previous_bauteil = getattr(self, 'previous_bauteil', None)
        is_rohrleitung_or_formteil = self.is_rohrleitung_or_formteil(bauteil)
        was_rohrleitung_or_formteil = self.is_rohrleitung_or_formteil(previous_bauteil)
        
        if bauteil:
            # Behalte die aktuellen Werte bei
            current_dn = self.dn_dropdown.value
            current_da = self.da_dropdown.value
            current_dammdicke = self.dammdicke_dropdown.value

            if is_rohrleitung_or_formteil:
                all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
                
                # Aktualisiere die Optionen
                self.dn_dropdown.options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
                self.da_dropdown.options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
                
                # Setze die Werte zurück, wenn sie in den neuen Optionen vorhanden sind
                if current_dn in [str(dn) for dn in all_dn_options]:
                    self.dn_dropdown.value = current_dn
                else:
                    self.dn_dropdown.value = str(all_dn_options[0]) if all_dn_options else None
                
                if current_da in [str(da) for da in all_da_options]:
                    self.da_dropdown.value = current_da
                else:
                    self.da_dropdown.value = str(all_da_options[0]) if all_da_options else None
                
                self.dn_dropdown.visible = True
                self.da_dropdown.visible = True
            else:
                self.dn_dropdown.options = []
                self.da_dropdown.options = []
                self.dn_dropdown.value = None
                self.da_dropdown.value = None
                self.dn_dropdown.visible = False
                self.da_dropdown.visible = False

            self.dn_dropdown.update()
            self.da_dropdown.update()
            
            # Aktualisiere die Dämmdicke-Optionen
            self.update_dammdicke_options()
            if current_dammdicke in [opt.key for opt in self.dammdicke_dropdown.options]:
                self.dammdicke_dropdown.value = current_dammdicke
            self.dammdicke_dropdown.update()
        
        # Aktualisiere den Preis, wenn sich der Bauteiltyp ändert oder wenn ein neues Bauteil ausgewählt wurde
        if bauteil != previous_bauteil or is_rohrleitung_or_formteil != was_rohrleitung_or_formteil:
            self.update_price()
        
        # Speichere das aktuelle Bauteil für den nächsten Vergleich
        self.previous_bauteil = bauteil
        
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def on_category_change(self, e):
        self.load_items(e)
        self.update_field_visibility()
        self.update()

    def load_all_dn_da_options(self, bauteil):
        all_dn_options = self.get_all_dn_options(bauteil)
        all_da_options = self.get_all_da_options(bauteil)
        return all_dn_options, all_da_options

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
        cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
        return cursor.fetchone() is not None

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
            cursor.execute("SELECT DISTINCT Positionsnummer, Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit' ORDER BY Positionsnummer")
        elif category == "Festpreis":
            cursor.execute("SELECT DISTINCT Positionsnummer, Bezeichnung FROM Faktoren WHERE Art = 'Formteil' ORDER BY Positionsnummer")

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
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
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

                # Erstelle die Optionen mit Trennern für das Artikelbeschreibung-Dropdown
                options = [
                    ft.dropdown.Option("Bauteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(bauteil) for bauteil in bauteile],
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

    def update_field_visibility(self):
        selected_category = self.category_dropdown.value

        # Setze zunächst alle Felder auf unsichtbar
        self.taetigkeit_dropdown.visible = False
        self.artikelbeschreibung_dropdown.visible = False
        self.dn_dropdown.visible = False
        self.da_dropdown.visible = False
        self.dammdicke_dropdown.visible = False
        self.quantity_input.visible = False
        self.price_field.visible = False
        self.zwischensumme_field.visible = False

        if selected_category == "Aufmaß":
            self.taetigkeit_dropdown.visible = True
            self.artikelbeschreibung_dropdown.visible = True
            self.dammdicke_dropdown.visible = True  # Immer sichtbar für Aufmaß
            self.quantity_input.visible = True
            self.price_field.visible = True
            self.zwischensumme_field.visible = True

            # Überprüfe, ob das ausgewählte Bauteil Rohrleitung oder Formteil ist
            bauteil = self.artikelbeschreibung_dropdown.value
            if self.is_rohrleitung_or_formteil(bauteil):
                self.dn_dropdown.visible = True
                self.da_dropdown.visible = True
            else:
                self.dn_dropdown.visible = False
                self.da_dropdown.visible = False

        elif selected_category in ["Material", "Lohn", "Festpreis"]:
            self.artikelbeschreibung_dropdown.visible = True
            self.quantity_input.visible = True
            self.price_field.visible = True
            self.zwischensumme_field.visible = True

        self.update()

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
        # Laden der Tätigkeiten aus der Faktoren-Tabelle
        cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit' ORDER BY Bezeichnung")
        taetigkeiten = [row[0] for row in cursor.fetchall()]
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]

        # Laden der Bauteile aus der price_list-Tabelle
        cursor.execute("SELECT DISTINCT Bauteil FROM price_list ORDER BY Bauteil")
        bauteile = [row[0] for row in cursor.fetchall()]
        self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(bauteil) for bauteil in bauteile]

        # Laden der DN-Optionen
        cursor.execute("SELECT DISTINCT DN FROM price_list WHERE DN IS NOT NULL ORDER BY DN")
        dn_options = [row[0] for row in cursor.fetchall()]
        self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in dn_options]

        # Laden der DA-Optionen
        cursor.execute("SELECT DISTINCT DA FROM price_list WHERE DA IS NOT NULL ORDER BY DA")
        da_options = [row[0] for row in cursor.fetchall()]
        self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]

        # Laden der Dämmdicke-Optionen
        cursor.execute("SELECT DISTINCT Size FROM price_list WHERE Size IS NOT NULL ORDER BY Size")
        dammdicke_options = [row[0] for row in cursor.fetchall()]
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(dammdicke)) for dammdicke in dammdicke_options]

        # Aktualisieren der UI-Elemente
        self.update()

    def load_other_options(self, cursor, category):
        if category == "Material":
            cursor.execute("SELECT Positionsnummer, Benennung FROM Materialpreise")
        elif category == "Lohn":
            cursor.execute("SELECT Positionsnummer, Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit'")
        elif category == "Festpreis":
            cursor.execute("SELECT Positionsnummer, Bezeichnung FROM Faktoren WHERE Art = 'Formteil'")

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
            except Exception as e:
                logging.error(f"Error loading options for {field}: {e}")
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
        try:
            cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
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

    def update_quantity(self, e):
        self.update_price()  # Aktualisiert die Zwischensumme
        self.update_total_price()  # Aktualisiert den Gesamtpreis
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

    def update_quantity(self, e):
        self.update_price()  # Aktualisiert die Zwischensumme
        self.update_total_price()  # Aktualisiert den Gesamtpreis