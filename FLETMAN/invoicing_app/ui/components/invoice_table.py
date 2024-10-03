import flet as ft
from database.db_operations import get_db_connection

class InvoiceTable(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.conn = get_db_connection()
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Beschreibung")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Größe")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
            ],
            rows=[]
        )

    def build(self):
        return self.data_table

    # Add other methods as needed