import flet as ft
from ui.components.invoice_form import InvoiceForm
from database.db_init import initialize_database

def main(page: ft.Page):
    initialize_database()  # Fügen Sie diese Zeile hinzu
    page.title = "KAEFER Industrie GmbH Abrechnungsprogramm 2024"
    invoice_form = InvoiceForm(page)  # Übergeben Sie die page an den Konstruktor
    page.add(invoice_form)

ft.app(target=main)
