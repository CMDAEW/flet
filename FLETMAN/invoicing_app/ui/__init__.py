import flet as ft
from .components.invoice_form import InvoiceForm
from .components.invoice_table import InvoiceTable
from database.db_operations import get_db_connection

class InvoicingApp(ft.UserControl):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.cursor = self.conn.cursor()
        self.items = []
        self.invoice_form = InvoiceForm(self)
        self.invoice_table = InvoiceTable(self)

    def build(self):
        return ft.Column([
            self.invoice_form,
            self.invoice_table,
            ft.Row([
                ft.ElevatedButton("Position hinzufügen", on_click=self.add_item),
                ft.ElevatedButton("Rechnung speichern", on_click=self.save_invoice),
                ft.ElevatedButton("PDF generieren", on_click=self.generate_pdf)
            ]),
        ])

    def add_item(self, e):
        self.invoice_table.add_item()

    def save_invoice(self, e):
        self.invoice_form.save_invoice()

    def generate_pdf(self, e):
        self.invoice_form.generate_pdf()

    def show_snackbar(self, message):
        if self.page:
            snack_bar = ft.SnackBar(content=ft.Text(message))
            self.page.snack_bar = snack_bar
            snack_bar.open = True
            self.page.update()
        else:
            print(f"Snackbar message (page not available): {message}")
