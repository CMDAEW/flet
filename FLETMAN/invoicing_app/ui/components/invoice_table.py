import flet as ft
from database.db_operations import get_taetigkeit_options, get_available_options, get_price

class InvoiceTable(ft.UserControl):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.items_container = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Beschreibung")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Größe")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen"))
            ],
            rows=[]
        )
        self.taetigkeit_options = get_taetigkeit_options(self.parent.conn)

    def build(self):
        return self.items_container

    def add_item(self):
        new_item = {
            "taetigkeit": ft.Dropdown(options=[ft.dropdown.Option(t) for t in self.taetigkeit_options]),
            "description": ft.Dropdown(options=[]),
            "dn": ft.Dropdown(options=[]),
            "da": ft.Dropdown(options=[]),
            "size": ft.Dropdown(options=[]),
            "price": ft.TextField(value="0.00", read_only=True),
            "quantity": ft.TextField(value="1"),
            "zwischensumme": ft.TextField(value="0.00", read_only=True),
        }
        self.parent.items.append(new_item)
        self.update_items_ui()

    def update_items_ui(self):
        self.items_container.rows.clear()
        for index, item in enumerate(self.parent.items):
            row = ft.DataRow(
                cells=[
                    ft.DataCell(item["taetigkeit"]),
                    ft.DataCell(item["description"]),
                    ft.DataCell(item["dn"]),
                    ft.DataCell(item["da"]),
                    ft.DataCell(item["size"]),
                    ft.DataCell(item["price"]),
                    ft.DataCell(item["quantity"]),
                    ft.DataCell(item["zwischensumme"]),
                    ft.DataCell(ft.IconButton(ft.icons.DELETE, on_click=lambda _, i=index: self.remove_item(i))),
                ]
            )
            self.items_container.rows.append(row)
        self.update()

    def remove_item(self, index):
        del self.parent.items[index]
        self.update_items_ui()

    def calculate_total(self):
        return sum(float(item["zwischensumme"].value) for item in self.parent.items if item["zwischensumme"].value)

    def update_price(self, item):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        price = get_price(self.parent.conn, bauteil, dn, da, size)
        item["price"].value = f"{price:.2f}"
        self.update_item_subtotal(item)

    def update_item_subtotal(self, item):
        price = float(item["price"].value)
        quantity = float(item["quantity"].value)
        subtotal = price * quantity
        item["zwischensumme"].value = f"{subtotal:.2f}"
        self.update_items_ui()
