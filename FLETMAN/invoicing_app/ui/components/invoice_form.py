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
                ft.dropdown.Option("Materialpreise"),
                ft.dropdown.Option("Arbeitsbescheinigung"),
                ft.dropdown.Option("Festpreise")
            ],
            on_change=self.load_items
        )
        self.item_dropdown = ft.Dropdown(label="Position")
        self.quantity_input = ft.TextField(label="Menge", value="1")
        self.add_button = ft.ElevatedButton("Position hinzufügen", on_click=self.add_item_to_invoice)

    def build(self):
        return ft.Column([
            self.category_dropdown,
            self.item_dropdown,
            self.quantity_input,
            self.add_button
        ])

    def load_items(self, e):
        selected_category = self.category_dropdown.value
        cursor = self.conn.cursor()
        
        if selected_category == "Aufmaß":
            cursor.execute("SELECT Positionsnummer, Bauteil FROM price_list")
        elif selected_category == "Materialpreise":
            cursor.execute("SELECT Positionsnummer, Benennung FROM Materialpreise")
        elif selected_category == "Arbeitsbescheinigung":
            cursor.execute("SELECT Positionsnummer, Taetigkeit FROM Taetigkeiten")
        elif selected_category == "Festpreise":
            cursor.execute("SELECT Positionsnummer, Formteile FROM Formteile")
        
        items = cursor.fetchall()
        self.item_dropdown.options = [ft.dropdown.Option(key=item[0], text=f"{item[0]} - {item[1]}") for item in items]
        self.update()

    def add_item_to_invoice(self, e):
        # Implementation for adding item to invoice
        pass
