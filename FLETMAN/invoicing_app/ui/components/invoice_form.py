import sqlite3
import flet as ft
from database.db_operations import get_db_connection
import asyncio

class InvoiceForm(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.conn = get_db_connection()

        # Initialize UI elements
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
        self.artikelbeschreibung_dropdown = ft.Dropdown(label="Artikelbeschreibung", on_change=self.update_dn_da_fields)
        self.dn_dropdown = ft.Dropdown(label="DN", on_change=self.update_da_fields)
        self.da_dropdown = ft.Dropdown(label="DA", on_change=self.update_dn_fields)
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=self.update_price)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=self.update_price)
        self.zuschlaege_dropdown = ft.Dropdown(label="Zuschläge", visible=False)
        self.position_field = ft.TextField(label="Position", read_only=True)
        self.price_field = ft.TextField(label="Preis", read_only=True)
        self.quantity_input = ft.TextField(label="Menge", value="1")
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True)
        self.add_button = ft.ElevatedButton("Position hinzufügen", on_click=self.add_item_to_invoice)

        # Invoice details fields
        self.client_name_dropdown = ft.Dropdown(label="Kunde", on_change=lambda e: self.toggle_new_entry(e, "client_name"))
        self.bestell_nr_dropdown = ft.Dropdown(label="Bestell-Nr.", on_change=lambda e: self.toggle_new_entry(e, "bestell_nr"))
        self.bestelldatum_dropdown = ft.Dropdown(label="Bestelldatum", on_change=lambda e: self.toggle_new_entry(e, "bestelldatum"))
        self.baustelle_dropdown = ft.Dropdown(label="Baustelle", on_change=lambda e: self.toggle_new_entry(e, "baustelle"))
        self.anlagenteil_dropdown = ft.Dropdown(label="Anlagenteil", on_change=lambda e: self.toggle_new_entry(e, "anlagenteil"))
        self.aufmass_nr_dropdown = ft.Dropdown(label="Aufmaß-Nr.", on_change=lambda e: self.toggle_new_entry(e, "aufmass_nr"))
        self.auftrags_nr_dropdown = ft.Dropdown(label="Auftrags-Nr.", on_change=lambda e: self.toggle_new_entry(e, "auftrags_nr"))
        self.ausfuehrungsbeginn_dropdown = ft.Dropdown(label="Ausführungsbeginn", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsbeginn"))
        self.ausfuehrungsende_dropdown = ft.Dropdown(label="Ausführungsende", on_change=lambda e: self.toggle_new_entry(e, "ausfuehrungsende"))

        # New entry fields for invoice details
        self.client_name_new_entry = ft.TextField(label="Neuer Kunde", visible=False)
        self.bestell_nr_new_entry = ft.TextField(label="Neue Bestell-Nr.", visible=False)
        self.bestelldatum_new_entry = ft.TextField(label="Neues Bestelldatum", visible=False)
        self.baustelle_new_entry = ft.TextField(label="Neue Baustelle", visible=False)
        self.anlagenteil_new_entry = ft.TextField(label="Neues Anlagenteil", visible=False)
        self.aufmass_nr_new_entry = ft.TextField(label="Neue Aufmaß-Nr.", visible=False)
        self.auftrags_nr_new_entry = ft.TextField(label="Neue Auftrags-Nr.", visible=False)
        self.ausfuehrungsbeginn_new_entry = ft.TextField(label="Neuer Ausführungsbeginn", visible=False)
        self.ausfuehrungsende_new_entry = ft.TextField(label="Neues Ausführungsende", visible=False)

        # Load initial data
        self.load_taetigkeiten()

    def load_taetigkeiten(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT Taetigkeit FROM Taetigkeiten ORDER BY Taetigkeit")
        taetigkeiten = cursor.fetchall()
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.value = None  # No preselection
        self.taetigkeit_dropdown.visible = True

    def build(self):
        # Load invoice options
        self.load_invoice_options()

        return ft.Column([
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
            ft.Container(height=50),  # Spacer
            # Item selection section
            ft.ResponsiveRow([
                ft.Column([self.position_field], col={"sm": 12, "md": 1}),
                ft.Column([self.taetigkeit_dropdown], col={"sm": 12, "md": 2}),
                ft.Column([self.artikelbeschreibung_dropdown], col={"sm": 12, "md": 2}),
                ft.Column([self.dn_dropdown], col={"sm": 12, "md": 1}),
                ft.Column([self.da_dropdown], col={"sm": 12, "md": 1}),
                ft.Column([self.dammdicke_dropdown], col={"sm": 12, "md": 1}),
                ft.Column([self.price_field], col={"sm": 12, "md": 1}),
                ft.Column([self.quantity_input], col={"sm": 12, "md": 1}),
                ft.Column([self.zwischensumme_field], col={"sm": 12, "md": 2}),
            ]),
            ft.ResponsiveRow([
                ft.Column([self.zuschlaege_dropdown], col={"sm": 12, "md": 6}),
                ft.Column([self.add_button], col={"sm": 12, "md": 6}),
            ]),
        ])

    def update_price(self, e=None):
        cursor = self.conn.cursor()
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
        da = self.da_dropdown.value if self.da_dropdown.visible else None
        size = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value

        if not bauteil or not size or not taetigkeit:
            # Reset price if required values are missing
            self.position_field.value = ""
            self.price_field.value = ""
            self.update()
            return

        # Check if it's a Formteil
        cursor.execute('SELECT Positionsnummer, Faktor FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
        formteil_result = cursor.fetchone()

        if formteil_result:
            position, formteil_factor = formteil_result
            # Get the base price for Rohrleitung
            cursor.execute('''
                SELECT Value
                FROM price_list
                WHERE Bauteil = 'Rohrleitung' AND DN = ? AND DA = ? AND Size = ?
            ''', (dn, da, size))
        elif self.is_rohrleitung_or_formteil(bauteil):
            cursor.execute('''
                SELECT Positionsnummer, Value
                FROM price_list
                WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?
            ''', (bauteil, dn, da, size))
        else:
            # For other Bauteile without DN and DA
            cursor.execute('''
                SELECT Positionsnummer, Value
                FROM price_list
                WHERE Bauteil = ? AND Size = ?
            ''', (bauteil, size))

        result = cursor.fetchone()

        if result:
            if formteil_result:
                base_price = float(result[0])
                base_price *= float(formteil_factor)
                position = formteil_result[0]
            else:
                position, base_price = result
                base_price = float(base_price)

            # Apply Tätigkeit factor
            cursor.execute('SELECT Faktor FROM Taetigkeiten WHERE Taetigkeit = ?', (taetigkeit,))
            taetigkeit_result = cursor.fetchone()
            if taetigkeit_result:
                factor = float(taetigkeit_result[0])
                base_price *= factor

            self.position_field.value = position
            self.price_field.value = f"{base_price:.2f}"  # Format to 2 decimal places
        else:
            self.position_field.value = ""
            self.price_field.value = ""

        self.update()

    def update_dn_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        da = self.da_dropdown.value
        if bauteil and da:
            corresponding_dn = self.get_corresponding_dn(bauteil, da)
            if corresponding_dn:
                self.dn_dropdown.value = str(corresponding_dn)
                self.dn_dropdown.update()
                self.dn_dropdown.visible = True
            self.update_dammdicke_fields(None)

        self.update_price()
        self.update()

    def update_da_fields(self, e):
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        if bauteil and dn:
            corresponding_da = self.get_corresponding_da(bauteil, dn)
            if corresponding_da:
                self.da_dropdown.value = str(corresponding_da)
                self.da_dropdown.update()
            self.update_dammdicke_fields(None)

        self.update_price()
        self.update()

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
            if self.is_rohrleitung_or_formteil(bauteil):
                dn_options = self.get_all_dn_options(bauteil)
                da_options = self.get_all_da_options(bauteil)
                self.dn_dropdown.options = [ft.dropdown.Option(str(dn)) for dn in dn_options]
                self.da_dropdown.options = [ft.dropdown.Option(str(da)) for da in da_options]
                self.dn_dropdown.visible = True
                self.da_dropdown.visible = True
            else:
                self.dn_dropdown.visible = False
                self.da_dropdown.visible = False

            # Always load and show Dämmdicke options
            dammdicke_options = self.get_dammdicke_options(bauteil)
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

        self.update()

    def reset_fields(self):
        for field in [self.position_field, self.price_field, self.zwischensumme_field]:
            field.value = ""
        for dropdown in [self.artikelbeschreibung_dropdown, self.taetigkeit_dropdown, self.dn_dropdown, self.da_dropdown, self.dammdicke_dropdown, self.zuschlaege_dropdown]:
            dropdown.options.clear()
            dropdown.visible = False
        self.quantity_input.visible = False

    def load_aufmass_options(self, cursor):
        # Load Tätigkeiten
        cursor.execute("SELECT DISTINCT Taetigkeit FROM Taetigkeiten ORDER BY Taetigkeit")
        taetigkeiten = cursor.fetchall()
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.visible = True

        # Load Zuschläge
        cursor.execute("SELECT DISTINCT Zuschlag FROM Zuschlaege ORDER BY Zuschlag")
        zuschlaege = cursor.fetchall()
        self.zuschlaege_dropdown.options = [ft.dropdown.Option(zuschlag[0]) for zuschlag in zuschlaege]
        self.zuschlaege_dropdown.visible = True

        # Load Bauteil (Artikelbeschreibung) and Formteile
        cursor.execute("SELECT DISTINCT Bauteil FROM price_list ORDER BY Bauteil")
        bauteile = cursor.fetchall()
        cursor.execute("SELECT DISTINCT Formteilbezeichnung FROM Formteile ORDER BY Formteilbezeichnung")
        self.formteile = cursor.fetchall()  # Store formteile data

        self.artikelbeschreibung_dropdown.options = [
            ft.dropdown.Option(b[0]) for b in bauteile
        ] + [
            ft.dropdown.Option("Formteile", disabled=True, text_style=ft.TextStyle(weight=ft.FontWeight.BOLD))
        ] + [
            ft.dropdown.Option(f[0]) for f in self.formteile
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
        # Implementation for adding item to invoice
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
        # Implement this based on how you're storing invoice items

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
        return bauteil == 'Rohrleitung' or self.is_formteil(bauteil)

    def is_formteil(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT 1 FROM Formteile WHERE Formteilbezeichnung = ?', (bauteil,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def get_corresponding_dn(self, bauteil, da):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                cursor.execute('SELECT dn FROM price_list WHERE bauteil = ? AND da = ? AND value IS NOT NULL AND value != 0 ORDER BY dn LIMIT 1', ('Rohrleitung', da))
            else:
                cursor.execute('SELECT dn FROM price_list WHERE bauteil = ? AND da = ? AND value IS NOT NULL AND value != 0 ORDER BY dn LIMIT 1', (bauteil, da))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def get_corresponding_da(self, bauteil, dn):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                cursor.execute('SELECT da FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY da LIMIT 1', ('Rohrleitung', dn))
            else:
                cursor.execute('SELECT da FROM price_list WHERE bauteil = ? AND dn = ? AND value IS NOT NULL AND value != 0 ORDER BY da LIMIT 1', (bauteil, dn))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()

    def get_all_dn_options(self, bauteil):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                cursor.execute('SELECT DISTINCT dn FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0 ORDER BY dn', ('Rohrleitung',))
            else:
                cursor.execute('SELECT DISTINCT dn FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0 ORDER BY dn', (bauteil,))
            return sorted(set(int(row[0]) for row in cursor.fetchall() if row[0] is not None and row[0] != 0))
        finally:
            cursor.close()

    def get_all_da_options(self, bauteil):
        conn = self.conn
        cursor = conn.cursor()
        try:
            if self.is_formteil(bauteil):
                cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0 ORDER BY da', ('Rohrleitung',))
            else:
                cursor.execute('SELECT DISTINCT da FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0 ORDER BY da', (bauteil,))
            return sorted(set(row[0] for row in cursor.fetchall() if row[0] is not None))
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
