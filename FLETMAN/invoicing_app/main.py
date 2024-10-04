import flet as ft
from ui.components.invoice_form import InvoiceForm

def main(page: ft.Page):
    page.title = "Rechnungsformular"
    invoice_form = InvoiceForm(page)  # Übergeben Sie die page an den Konstruktor
    page.add(invoice_form)

ft.app(target=main)
