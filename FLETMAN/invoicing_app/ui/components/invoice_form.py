import flet as ft
from database.db_operations import get_db_connection

class InvoiceForm(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.conn = get_db_connection()
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
        self.artikelbeschreibung_dropdown = ft.Dropdown(label="Artikelbeschreibung", on_change=self.update_fields)
        self.dn_dropdown = ft.Dropdown(label="DN", visible=False, on_change=self.update_fields)
        self.da_dropdown = ft.Dropdown(label="DA", visible=False, on_change=self.update_fields)
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", visible=False, on_change=self.update_fields)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", visible=False, on_change=self.update_fields)
        self.zuschlaege_dropdown = ft.Dropdown(label="Zuschläge", visible=False)
        self.position_field = ft.TextField(label="Position", read_only=True)
        self.price_field = ft.TextField(label="Preis", read_only=True)
        self.quantity_input = ft.TextField(label="Menge", value="1")
        self.zwischensumme_field = ft.TextField(label="Zwischensumme", read_only=True)
        self.add_button = ft.ElevatedButton("Position hinzufügen", on_click=self.add_item_to_invoice)

    def build(self):
        return ft.Column([
            self.category_dropdown,
            self.artikelbeschreibung_dropdown,
            self.taetigkeit_dropdown,
            self.dn_dropdown,
            self.da_dropdown,
            self.dammdicke_dropdown,
            self.zuschlaege_dropdown,
            self.position_field,
            self.price_field,
            self.quantity_input,
            self.zwischensumme_field,
            self.add_button
        ])

    def load_items(self, e):
        selected_category = self.category_dropdown.value
        cursor = self.conn.cursor()
        
        # Reset all fields
        self.position_field.value = ""
        self.price_field.value = ""
        self.zwischensumme_field.value = ""
        self.artikelbeschreibung_dropdown.options.clear()
        self.taetigkeit_dropdown.options.clear()
        self.dn_dropdown.options.clear()
        self.da_dropdown.options.clear()
        self.dammdicke_dropdown.options.clear()
        self.zuschlaege_dropdown.options.clear()
        
        # Hide all fields by default
        self.artikelbeschreibung_dropdown.visible = False
        self.taetigkeit_dropdown.visible = False
        self.dn_dropdown.visible = False
        self.da_dropdown.visible = False
        self.dammdicke_dropdown.visible = False
        self.zuschlaege_dropdown.visible = False
        self.position_field.visible = False
        self.price_field.visible = False
        self.quantity_input.visible = False
        self.zwischensumme_field.visible = False

        if selected_category == "Aufmaß":
            cursor.execute("SELECT DISTINCT Bauteil FROM price_list UNION SELECT DISTINCT Formteilbezeichnung FROM Formteile")
            bauteile = cursor.fetchall()
            self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(bauteil[0]) for bauteil in bauteile]
            
            cursor.execute("SELECT DISTINCT Taetigkeit FROM Taetigkeiten")
            taetigkeiten = cursor.fetchall()
            self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit[0]) for taetigkeit in taetigkeiten]
            
            self.artikelbeschreibung_dropdown.visible = True
            self.taetigkeit_dropdown.visible = True
            self.dn_dropdown.visible = True
            self.da_dropdown.visible = True
            self.dammdicke_dropdown.visible = True
            self.zuschlaege_dropdown.visible = True
            self.position_field.visible = True
            self.price_field.visible = True
            self.quantity_input.visible = True
            self.zwischensumme_field.visible = True
            self.load_dn_da_options()
            self.load_zuschlaege_options()
        elif selected_category in ["Material", "Lohn", "Festpreis"]:
            if selected_category == "Material":
                cursor.execute("SELECT Positionsnummer, Benennung FROM Materialpreise")
            elif selected_category == "Lohn":
                cursor.execute("SELECT Positionsnummer, Taetigkeit FROM Taetigkeiten")
            elif selected_category == "Festpreis":
                cursor.execute("SELECT Positionsnummer, Formteilbezeichnung FROM Formteile")
            
            items = cursor.fetchall()
            self.artikelbeschreibung_dropdown.options = [ft.dropdown.Option(key=item[0], text=f"{item[0]} - {item[1]}") for item in items]
            self.artikelbeschreibung_dropdown.visible = True
            self.position_field.visible = True
            self.price_field.visible = True
            self.quantity_input.visible = True
            self.zwischensumme_field.visible = True

        self.update()

    def update_fields(self, e):
        if self.category_dropdown.value == "Aufmaß":
            self.update_position_and_price()

    def update_position_and_price(self):
        cursor = self.conn.cursor()
        bauteil = self.artikelbeschreibung_dropdown.value
        dn = self.dn_dropdown.value
        da = self.da_dropdown.value
        size = self.dammdicke_dropdown.value

        cursor.execute('''
            SELECT Positionsnummer, Value
            FROM price_list
            WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?
        ''', (bauteil, dn, da, size))
        result = cursor.fetchone()

        if result:
            self.position_field.value = result[0]
            # You might want to display the price somewhere in your form
            # self.price_field.value = result[1]
        else:
            self.position_field.value = ""
            # self.price_field.value = ""

        self.update()

    def load_dn_da_options(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT DN FROM price_list WHERE DN != 0 ORDER BY DN")
        dn_options = cursor.fetchall()
        self.dn_dropdown.options = [ft.dropdown.Option(str(dn[0])) for dn in dn_options]

        cursor.execute("SELECT DISTINCT DA FROM price_list WHERE DA != 0 ORDER BY DA")
        da_options = cursor.fetchall()
        self.da_dropdown.options = [ft.dropdown.Option(str(da[0])) for da in da_options]

        cursor.execute("SELECT DISTINCT Size FROM price_list WHERE Size != '' ORDER BY Size")
        dammdicke_options = cursor.fetchall()
        self.dammdicke_dropdown.options = [ft.dropdown.Option(size[0]) for size in dammdicke_options]

    def load_zuschlaege_options(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT Positionsnummer, Zuschlag FROM Zuschlaege")
        zuschlaege = cursor.fetchall()
        self.zuschlaege_dropdown.options = [ft.dropdown.Option(key=z[0], text=f"{z[0]} - {z[1]}") for z in zuschlaege]

    def add_item_to_invoice(self, e):
        # Implementation for adding item to invoice
        pass