import flet as ft
from flet import DataTable, DataColumn, DataRow, DataCell, IconButton, icons
from database.db_operations import get_db_connection
import logging

def show_edit_invoice_dialog(page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu_func):
    invoices = get_existing_invoices()
    
    dialog = ft.AlertDialog(
        modal=True,  # Dies verhindert Klicks außerhalb des Dialogs
        title=ft.Text("Existierende Aufmaße", size=20, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=build_invoice_list_content(invoices, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, page),
            width=650,
            height=400,
            border=ft.border.all(1, ft.colors.GREY_400),
            border_radius=10,
            padding=10,
        ),
        actions=[
            ft.TextButton("Schließen", on_click=lambda _: close_edit_invoice_dialog(page, back_to_main_menu_func)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.dialog = dialog
    dialog.open = True
    page.update()

def build_invoice_list_content(invoices, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, page):
    rows = []
    for invoice in sorted(invoices, key=lambda x: int(x['aufmass_nr'])):
        rows.append(
            DataRow(
                cells=[
                    DataCell(ft.Text(invoice['aufmass_nr'])),
                    DataCell(ft.Text(invoice['client_name'])),
                    DataCell(ft.Text(f"{invoice['total_amount']:.2f} €")),
                    DataCell(
                        ft.Row([
                            IconButton(
                                icon=icons.EDIT,
                                icon_color="blue400",
                                tooltip="Bearbeiten",
                                on_click=lambda _, inv=invoice: load_invoice_for_editing(inv['aufmass_nr'], on_invoice_selected, page)
                            ),
                            IconButton(
                                icon=icons.EURO_SYMBOL,
                                icon_color="green400",
                                tooltip="PDF mit Preisen",
                                on_click=lambda _, inv=invoice: on_pdf_with_prices(inv['aufmass_nr'])
                            ),
                            IconButton(
                                icon=icons.DESCRIPTION,
                                icon_color="orange400",
                                tooltip="PDF ohne Preise",
                                on_click=lambda _, inv=invoice: on_pdf_without_prices(inv['aufmass_nr'])
                            )
                        ])
                    )
                ],
                on_select_changed=lambda e, inv=invoice: preview_invoice(inv['aufmass_nr'], on_invoice_preview)
            )
        )
    
    return ft.ListView(
        controls=[
            DataTable(
                columns=[
                    DataColumn(ft.Text("Aufmaß-Nr.")),
                    DataColumn(ft.Text("Kunde")),
                    DataColumn(ft.Text("Summe")),
                    DataColumn(ft.Text("Aktionen"))
                ],
                rows=rows,
                border=ft.border.all(1, ft.colors.GREY_400),
                vertical_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
                horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
            )
        ],
        expand=True,
        auto_scroll=False
    )

def get_existing_invoices():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT aufmass_nr, client_name, total_amount
            FROM invoice
            ORDER BY CAST(aufmass_nr AS INTEGER) ASC
        ''')
        return [{'aufmass_nr': row[0], 'client_name': row[1], 'total_amount': row[2]} for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def preview_invoice(aufmass_nr, on_invoice_preview):
    on_invoice_preview(aufmass_nr)

def load_invoice_for_editing(aufmass_nr, on_invoice_selected, page):
    close_edit_invoice_dialog(page, lambda: None)
    on_invoice_selected(aufmass_nr)
    page.update()
    if hasattr(page, 'invoice_form'):
        page.invoice_form.enable_all_inputs()
        page.invoice_form.update_topbar()
        page.update()

def close_edit_invoice_dialog(page, back_to_main_menu_func):
    if hasattr(page, 'dialog'):
        page.dialog.open = False
        page.update()
    back_to_main_menu_func()  # Ruft die Funktion auf, um zum Hauptmenü zurückzukehren

def back_to_main_menu(page):
    close_edit_invoice_dialog(page)
    page.go('/')

def delete_invoice_dialog(page):
    # Implement delete functionality
    pass

def print_invoice_dialog(page):
    # Implement print functionality
    pass
