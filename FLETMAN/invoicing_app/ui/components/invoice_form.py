import logging
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
        self.cache = {}
        self.article_summaries = []
        
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        
        # Rechnungskopf Dropdowns und Textfelder
        self.client_name_dropdown = ft.Dropdown(label="Kunde", on_change=lambda e: self.toggle_new_entry(e, "client_name"))
        self.client_name_new_entry = ft.TextField(label="Neuer Kunde", visible=False)
        self.bestell_nr_dropdown = ft.Dropdown(label="Bestell-Nr.", on_change=lambda e: self.toggle_new_entry(e, "bestell_nr"))
        self.bestell_nr_new_entry = ft.TextField(label="Neue Bestell-Nr.", visible=False)
        self.bestelldatum_dropdown = ft.Dropdown(label="Bestelldatum", on_change=lambda e: self.toggle_new_entry(e, "bestelldatum"))
        self.bestelldatum_new_entry = ft.TextField(label="Neues Bestelldatum", visible=False)
        self.baustelle_dropdown = ft.Dropdown(label="Baustelle", on_change=lambda e: self.toggle_new_entry(e, "baustelle"))
        self.baustelle_new_entry = ft.TextField(label="Neue Baustelle", visible=False)
        self.anlagenteil_dropdown = ft.Dropdown(label="Anlagenteil", on_change=lambda e: self.toggle_new_entry(e, "anlagenteil"))
        self.anlagenteil_new_entry = ft.TextField(label="Neues Anlagenteil", visible=False)
        self.aufmass_nr_dropdown = ft.Dropdown(label="Aufmaß-Nr.", on_change=lambda e: self.toggle_new_entry(e, "aufmass_nr"))
        self.aufmass_nr_new_entry = ft.TextField(label="Neue Aufmaß-Nr.", visible=False)
        self.auftrags_nr_dropdown = ft.Dropdown(label="Auftrags-Nr.", on_change=lambda e: self.toggle_new_entry(e, "auftrags_nr"))
        self.auftrags_nr_new_entry = ft.TextField(label="Neue Auftrags-Nr.", visible=False)
        self.ausfuehrungsbeginn_dropdown = ft.Dropdown(label="Ausführungsbeginn", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsbeginn"))
        self.ausfuehrungsbeginn_new_entry = ft.TextField(label="Neuer Ausführungsbeginn", visible=False)
        self.ausfuehrungsende_dropdown = ft.Dropdown(label="Ausführungsende", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsende"))
        self.ausfuehrungsende_new_entry = ft.TextField(label="Neues Ausführungsende", visible=False)
        
        self.category_dropdown = ft.Dropdown(
            label="Kategorie",
            options=[
                ft.dropdown.Option("Aufmaß"),
                ft.dropdown.Option("Material"),
                ft.dropdown.Option("Lohn"),
                ft.dropdown.Option("Festpreis")
            ],
            width=200,
            on_change=self.on_category_change
        )
        
        self.taetigkeit_dropdown = ft.Dropdown(
            label="Tätigkeit",
            width=200,
            visible=False
        )
        
        self.artikelbeschreibung_dropdown = ft.Dropdown(
            label="Artikelbeschreibung",
            width=200,
            on_change=self.update_dn_da_fields
        )
        
        self.dn_dropdown = ft.Dropdown(
            label="DN",
            width=100,
            visible=False
        )
        
        self.da_dropdown = ft.Dropdown(
            label="DA",
            width=100,
            visible=False
        )
        
        self.dammdicke_dropdown = ft.Dropdown(
            label="Dämmdicke",
            width=150,
            visible=False
        )
        
        self.quantity_input = ft.TextField(
            label="Menge",
            width=100,
            on_change=self.update_price
        )
        
        self.price_field = ft.TextField(
            label="Preis",
            width=150,
            read_only=True
        )
        
        self.zwischensumme_field = ft.TextField(
            label="Zwischensumme",
            width=150,
            read_only=True
        )
        
        self.position_field = ft.TextField(
            label="Position",
            width=100,
            read_only=True
        )
        
        self.sonderleistungen_button = ft.ElevatedButton(
            "Sonderleistungen",
            on_click=self.show_sonderleistungen_dialog
        )
        
        self.zuschlaege_button = ft.ElevatedButton(
            "Zuschläge",
            on_click=self.show_zuschlaege_dialog
        )
        
        self.sonderleistungen_container = ft.Container(
            content=ft.Column(controls=[]),
            visible=False
        )
        self.zuschlaege_container = ft.Container(
            content=ft.Column(controls=[]),
            visible=False
        )
        
        self.total_price_field = ft.TextField(
            label="Gesamtsumme",
            value="0.00",
            read_only=True,
            width=150
        )
        
        # Initialisiere die Faktoren
        self.load_faktoren("Sonderleistung")
        self.load_faktoren("Zuschlag")

    def on_category_change(self, e):
        self.load_items()
        self.update_field_visibility()
        self.update()

    def load_items(self):
        category = self.category_dropdown.value
        if not category:
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            if category == "Aufmaß":
                # Lade alle Bauteile mit ihren Dämmdicken
                cursor.execute("SELECT DISTINCT Bauteil, Size FROM price_list ORDER BY Bauteil")
                bauteil_data = cursor.fetchall()

                bauteile = []
                kleinkram = []

                for bauteil, size in bauteil_data:
                    if ' - ' in str(size):  # Wenn die Dämmdicke einen Bereich hat
                        if bauteil not in kleinkram:
                            kleinkram.append(bauteil)
                    else:
                        if bauteil not in bauteile:
                            bauteile.append(bauteil)

                # Lade Formteile aus der Faktoren Tabelle
                cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Formteil' ORDER BY Bezeichnung")
                formteile = [row[0] for row in cursor.fetchall()]

                # Erstelle die Optionen mit Trennern
                options = [
                    ft.dropdown.Option("Bauteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(bauteil) for bauteil in bauteile],
                    ft.dropdown.Option("Formteil", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(formteil) for formteil in formteile],
                    ft.dropdown.Option("Kleinkram", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)),
                    *[ft.dropdown.Option(item) for item in kleinkram]
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
        category = self.category_dropdown.value

        self.taetigkeit_dropdown.visible = category == "Aufmaß"
        self.dammdicke_dropdown.visible = category == "Aufmaß"
        self.dn_dropdown.visible = category == "Aufmaß" and self.is_rohrleitung_or_formteil(self.artikelbeschreibung_dropdown.value)
        self.da_dropdown.visible = category == "Aufmaß" and self.is_rohrleitung_or_formteil(self.artikelbeschreibung_dropdown.value)

        self.artikelbeschreibung_dropdown.visible = True
        self.quantity_input.visible = True
        self.price_field.visible = True
        self.zwischensumme_field.visible = True

        self.update()

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
        self.update_field_visibility()
        self.update_price()
        self.update()

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

    def show_zuschlaege_dialog(self, e):
        dialog = ft.AlertDialog(
            title=ft.Text("Zuschläge"),
            content=self.zuschlaege_container,
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_dialog()),
                ft.TextButton("Anwenden", on_click=self.apply_zuschlaege)
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def close_dialog(self):
        self.page.dialog.open = False
        self.page.update()

    def apply_zuschlaege(self, e):
        # Implementieren Sie hier die Logik zum Anwenden der ausgewählten Zuschläge
        self.page.dialog.open = False
        self.page.update()
        self.update_price()

    def show_sonderleistungen_dialog(self, e):
        dialog = ft.AlertDialog(
            title=ft.Text("Sonderleistungen"),
            content=self.sonderleistungen_container,
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_dialog()),
                ft.TextButton("Anwenden", on_click=self.apply_sonderleistungen)
            ]
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def apply_sonderleistungen(self, e):
        # Implementieren Sie hier die Logik zum Anwenden der ausgewählten Sonderleistungen
        self.page.dialog.open = False
        self.page.update()
        self.update_price()

    def update_field_visibility(self):
        category = self.category_dropdown.value

        # Setzen Sie die Sichtbarkeit der Felder basierend auf der ausgewählten Kategorie
        self.taetigkeit_dropdown.visible = category == "Aufmaß"
        self.dammdicke_dropdown.visible = category == "Aufmaß"
        self.dn_dropdown.visible = category == "Aufmaß" and self.is_rohrleitung_or_formteil(self.artikelbeschreibung_dropdown.value)
        self.da_dropdown.visible = category == "Aufmaß" and self.is_rohrleitung_or_formteil(self.artikelbeschreibung_dropdown.value)

        # Aktualisieren Sie hier weitere Felder nach Bedarf

        self.update()

    # ... (Rest der Klasse)

    def get_sonderleistungen(self):
        return self.get_faktoren("Sonderleistung")

    def get_zuschlaege(self):
        return self.get_faktoren("Zuschläge")

    def get_faktoren(self, art):
        cursor = self.conn.cursor()
        cursor.execute("SELECT Bezeichnung FROM Faktoren WHERE Art = ?", (art,))
        faktoren = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return faktoren

    def build(self):
        # Rechnungskopf
        invoice_header = ft.Column([
            ft.Row([self.client_name_dropdown, self.client_name_new_entry]),
            ft.Row([self.bestell_nr_dropdown, self.bestell_nr_new_entry]),
            ft.Row([self.bestelldatum_dropdown, self.bestelldatum_new_entry]),
            ft.Row([self.baustelle_dropdown, self.baustelle_new_entry]),
            ft.Row([self.anlagenteil_dropdown, self.anlagenteil_new_entry]),
            ft.Row([self.aufmass_nr_dropdown, self.aufmass_nr_new_entry]),
            ft.Row([self.auftrags_nr_dropdown, self.auftrags_nr_new_entry]),
            ft.Row([self.ausfuehrungsbeginn_dropdown, self.ausfuehrungsbeginn_new_entry]),
            ft.Row([self.ausfuehrungsende_dropdown, self.ausfuehrungsende_new_entry]),
        ])

        # Artikeleingabezeile
        article_input = ft.Row([
            self.position_field,
            self.category_dropdown,
            self.artikelbeschreibung_dropdown,
            self.taetigkeit_dropdown,
            self.dn_dropdown,
            self.da_dropdown,
            self.dammdicke_dropdown,
            self.quantity_input,
            self.price_field,
            self.zwischensumme_field,
            ft.ElevatedButton("Sonderleistungen", on_click=self.show_sonderleistungen_dialog),
            ft.ElevatedButton("Zuschläge", on_click=self.show_zuschlaege_dialog),
            ft.ElevatedButton("Hinzufügen", on_click=self.add_item),
        ])

        # Artikelliste
        self.article_list = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Pos")),
                ft.DataColumn(ft.Text("Kategorie")),
                ft.DataColumn(ft.Text("Artikel")),
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Dämmdicke")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen")),
            ],
            rows=[]
        )

        # Gesamtsumme
        total_row = ft.Row([
            ft.Text("Gesamtsumme:"),
            self.total_price_field,
        ], alignment=ft.MainAxisAlignment.END)

        return ft.Column([
            invoice_header,
            article_input,
            self.article_list,
            total_row,
            ft.ElevatedButton("Rechnung erstellen", on_click=self.create_invoice),
        ])

    def load_faktoren(self, art):
        cursor = self.conn.cursor()
        cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        faktoren = cursor.fetchall()
        
        container = self.sonderleistungen_container if art == "Sonderleistung" else self.zuschlaege_container
        column = container.content
        column.controls.clear()
        
        for bezeichnung, faktor in faktoren:
            checkbox = ft.Checkbox(label=f"{bezeichnung}", value=False)
            if art == "Sonderleistung":
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_sonderleistungen(e, b, f)
            else:
                checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_zuschlaege(e, b, f)
            column.controls.append(checkbox)
        
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

    def sort_dammdicke(self, size):
        if ' - ' in size:
            return int(size.split(' - ')[0])
        try:
            return int(size)
        except ValueError:
            return size

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
                return None  # Für andere Kategorien

            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()
    
    def load_items(self, e=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            self.load_aufmass_options(cursor)
            # Hier können Sie weitere Daten laden, falls erforderlich
        except sqlite3.Error as error:
            logging.error(f"Error loading items: {error}")
        finally:
            cursor.close()
            conn.close()

    def toggle_new_entry(self, e, field_name):
        dropdown = getattr(self, f"{field_name}_dropdown")
        new_entry = getattr(self, f"{field_name}_new_entry")
        
        if dropdown.value == "Neuer Eintrag":
            new_entry.visible = True
        else:
            new_entry.visible = False
        
        self.update()
        
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        size = self.dammdicke_dropdown.value if self.dammdicke_dropdown.visible else None
        taetigkeit = self.taetigkeit_dropdown.value
        position = self.position_field.value
        price = self.price_field.value
        quantity = self.quantity_input.value
        zwischensumme = self.zwischensumme_field.value

        print(f"Added item: Position: {position}, Price: {price}, Quantity: {quantity}, Zwischensumme: {zwischensumme}")

        self.reset_item_fields()

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
                return None  # Für andere Kategorien

            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def is_rohrleitung_or_formteil(self, bauteil):
        # Implementieren Sie hier die Logik zur Überprüfung, ob es sich um eine Rohrleitung oder ein Formteil handelt
        # Zum Beispiel:
        return bauteil in ["Rohrleitung", "Bogen", "T-Stück", "Reduzierung"]  # Erweitern Sie diese Liste nach Bedarf
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

    def update_dammdicke_options(self, bauteil):
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None

        dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
        self.dammdicke_dropdown.options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        
        # Setze den ersten verfügbaren Wert
        if dammdicke_options:
            self.dammdicke_dropdown.value = str(dammdicke_options[0])
        else:
            self.dammdicke_dropdown.value = None

        self.update()

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

    def create_invoice(self, e):
    # Hier implementieren Sie die Logik zum Erstellen der Rechnung
    # Dies könnte das Generieren eines PDF-Dokuments oder das Speichern in einer Datenbank beinhalten
        print("Rechnung wird erstellt...")  # Vorübergehende Ausgabe für Testzwecke
    
    # Beispiel für das Sammeln der Rechnungsdaten
        invoice_data = {
            "client": self.client_name_dropdown.value,
            "order_number": self.bestell_nr_dropdown.value,
            "order_date": self.bestelldatum_dropdown.value,
            "construction_site": self.baustelle_dropdown.value,
            "plant_part": self.anlagenteil_dropdown.value,
            "measurement_number": self.aufmass_nr_dropdown.value,
                        "order_number": self.auftrags_nr_dropdown.value,
            "execution_start": self.ausfuehrungsbeginn_dropdown.value,
            "execution_end": self.ausfuehrungsende_dropdown.value,
            "items": self.items,
            "total_price": self.total_price_field.value
    }
    
    # Hier würden Sie die Logik zum Speichern oder Drucken der Rechnung implementieren
    # Zum Beispiel:
        # self.save_invoice_to_database(invoice_data)
        # self.generate_invoice_pdf(invoice_data)
    
        # Zeigen Sie eine Bestätigungsnachricht an
        self.page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung wurde erstellt!"))
        self.page.snack_bar.open = True
        self.page.update()

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

    def add_item(self, e):
        category = self.category_dropdown.value
        bauteil = self.artikelbeschreibung_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        dammdicke = self.dammdicke_dropdown.value
        quantity = self.quantity_input.value
        price = self.price_field.value
        zwischensumme = self.zwischensumme_field.value

        if not category:
            self.show_error("Bitte wählen Sie eine Kategorie aus.")
            return

        required_fields = [bauteil, quantity, price, zwischensumme]
        if category == "Aufmaß":
            required_fields.extend([taetigkeit, dammdicke])

        if not all(required_fields):
            self.show_error("Bitte füllen Sie alle erforderlichen Felder aus.")
            return

        item = {
            "category": category,
            "bauteil": bauteil,
            "taetigkeit": taetigkeit if category == "Aufmaß" else None,
            "dn": dn,
            "da": da,
            "dammdicke": dammdicke if category == "Aufmaß" else None,
            "quantity": quantity,
            "price": price,
            "zwischensumme": zwischensumme,
            "sonderleistungen": [sl for sl, checked in self.selected_sonderleistungen if checked],
            "zuschlaege": [z for z, checked in self.selected_zuschlaege if checked]
        }

        if not hasattr(self, 'items'):
            self.items = []
        self.items.append(item)

        self.update_items_display()
        self.reset_form_fields()
        self.update_total_price()
        self.update()

    def remove_item(self, item):
        self.items.remove(item)
        self.update_items_display()
        self.update_total_price()
        self.update()

    def remove_zwischensumme(self, index):
        # Entferne eine Zwischensumme an der gegebenen Position
        del self.article_summaries[index]
        self.update_total_price()  # Aktualisiere den Gesamtpreis

    def update_quantity(self, e):
        self.update_price()  # Aktualisiert die Zwischensumme
        self.update_total_price()  # Aktualisiert den Gesamtpreis

    def update_items_display(self):
        # Implementieren Sie hier die Logik zur Aktualisierung der Anzeige der hinzugefügten Artikel
        # Dies könnte eine Tabelle oder eine Liste sein, die alle hinzugefügten Artikel anzeigt
        pass

    def reset_form_fields(self):
        self.category_dropdown.value = None
        self.artikelbeschreibung_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.dn_dropdown.value = None
        self.da_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.quantity_input.value = None
        self.price_field.value = None
        self.zwischensumme_field.value = None
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        self.update_field_visibility()
        self.update()

    def update_total_sum(self):
        # Berechnen und aktualisieren Sie hier die Gesamtsumme aller hinzugefügten Artikel
        total_sum = sum(float(item['zwischensumme']) for item in self.items)
        # Aktualisieren Sie ein Feld oder Label mit der Gesamtsumme
        # Beispiel: self.total_sum_field.value = f"{total_sum:.2f}"
        self.update()