import flet as ft
from ui.components.invoice_form import InvoiceForm
from database.db_init import initialize_database

def main(page: ft.Page):
    page.title = "Rechnungserstellung"
    
    # Setzen Sie eine angemessene Fenstergröße
    page.window_width = 1200
    page.window_height = 800
    page.window_resizable = True
    page.window_maximized = True  # Startet die Anwendung maximiert

    # Erstellen Sie das InvoiceForm-Objekt
    invoice_form = InvoiceForm(page)

    # Fügen Sie das InvoiceForm zum Seitenlayout hinzu
    page.add(invoice_form)

    page.update()

if __name__ == "__main__":
    ft.app(target=main)
