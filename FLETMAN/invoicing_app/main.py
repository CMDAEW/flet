import flet as ft
from ui.components.invoice_form import InvoiceForm
from ui.components.invoice_table import InvoiceTable
from database.db_init import initialize_database

def main(page: ft.Page):
    initialize_database()
    invoice_form = InvoiceForm()
    invoice_table = InvoiceTable()
    
    page.add(
        ft.Column([
            invoice_form,
            invoice_table,
            ft.ElevatedButton("Save Invoice", on_click=lambda _: save_invoice(invoice_form, invoice_table))
        ])
    )

    page.theme = ft.Theme(
        scrollbar_theme=ft.ScrollbarTheme(
            thickness=10,
            radius=3,
            main_axis_margin=4,
            cross_axis_margin=2,
            thumb_color="blue",
            track_color="lightblue",
        )
    )

def save_invoice(form, table):
    # Implement save logic
    pass

if __name__ == "__main__":
    ft.app(target=main)
