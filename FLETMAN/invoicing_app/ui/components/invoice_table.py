import flet as ft
from database.db_operations import get_db_connection

class InvoiceTable(ft.UserControl):
    def __init__(self):
        super().__init__()
        self.conn = get_db_connection()
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Positionsnummer")),
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("DN")),
                ft.DataColumn(ft.Text("DA")),
                ft.DataColumn(ft.Text("Größe")),
                ft.DataColumn(ft.Text("Einheit")),
                ft.DataColumn(ft.Text("Bauteil")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Zwischensumme")),
            ],
            rows=[]
        )

    def build(self):
        return self.data_table

    def update_table(self, invoice_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT Positionsnummer, taetigkeit, DN, DA, Size, Unit, Bauteil, Value, quantity, zwischensumme
            FROM invoice_items
            WHERE invoice_id = ?
        ''', (invoice_id,))
        rows = cursor.fetchall()
        
        self.data_table.rows.clear()
        for row in rows:
            self.data_table.rows.append(
                ft.DataRow(
                    cells=[ft.DataCell(ft.Text(str(cell))) for cell in row]
                )
            )
        self.update()

    # Add other methods as needed