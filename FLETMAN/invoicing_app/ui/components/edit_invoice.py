import flet as ft
from flet import DataTable, DataColumn, DataRow, DataCell, IconButton, icons
from database.db_operations import get_db_connection
import logging
import sqlite3

def show_edit_invoice_dialog(page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu_func):
    invoices = get_existing_invoices()
    
    dialog = ft.AlertDialog(
        modal=True,  # Dies verhindert Klicks außerhalb des Dialogs
        title=ft.Text("Existierende Aufmaße", size=20, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=build_invoice_list_content(invoices, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, page, back_to_main_menu_func),
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

def build_invoice_list_content(invoices, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, page, back_to_main_menu_func):
    rows = []
    for invoice in sorted(invoices, key=lambda x: int(x['aufmass_nr'])):
        if invoice['deleted']:
            # Für gelöschte Aufmaße
            rows.append(
                DataRow(
                    cells=[
                        DataCell(ft.Text(invoice['aufmass_nr'])),
                        DataCell(ft.Text("GELÖSCHT", style=ft.TextStyle(color=ft.colors.RED))),
                        DataCell(ft.Text("")),  # Leere Zelle für Summe
                        DataCell(ft.Text(""))   # Leere Zelle für Aktionen
                    ],
                )
            )
        else:
            # Für aktive Aufmaße
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
                                ),
                                IconButton(
                                    icon=icons.DELETE,
                                    icon_color="red400",
                                    tooltip="Löschen",
                                    on_click=lambda _, inv=invoice: confirm_delete_invoice(inv['aufmass_nr'], page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu_func)
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
            SELECT aufmass_nr, client_name, total_amount, deleted
            FROM invoice
            ORDER BY CAST(aufmass_nr AS INTEGER) ASC
        ''')
        return [{'aufmass_nr': row[0], 'client_name': row[1], 'total_amount': row[2], 'deleted': row[3]} for row in cursor.fetchall()]
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

def delete_invoice(aufmass_nr, page):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Prüfen, ob es das aktuellste Aufmaß ist
        cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
        max_aufmass_nr = cursor.fetchone()[0]
        
        if int(aufmass_nr) == max_aufmass_nr:
            # Wenn es das aktuellste Aufmaß ist, löschen wir es komplett
            cursor.execute("DELETE FROM invoice WHERE aufmass_nr = ?", (aufmass_nr,))
            cursor.execute("DELETE FROM invoice_items WHERE invoice_id = (SELECT id FROM invoice WHERE aufmass_nr = ?)", (aufmass_nr,))
        else:
            # Sonst markieren wir es als gelöscht
            cursor.execute("UPDATE invoice SET deleted = 1, client_name = 'GELÖSCHT' WHERE aufmass_nr = ?", (aufmass_nr,))
            cursor.execute("DELETE FROM invoice_items WHERE invoice_id = (SELECT id FROM invoice WHERE aufmass_nr = ?)", (aufmass_nr,))
        
        conn.commit()
        show_snack_bar(page, f"Aufmaß Nr. {aufmass_nr} wurde gelöscht.")
    except sqlite3.Error as e:
        conn.rollback()
        show_snack_bar(page, f"Fehler beim Löschen des Aufmaßes: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def show_snack_bar(page, message):
    page.snack_bar = ft.SnackBar(content=ft.Text(message))
    page.snack_bar.open = True
    page.update()

def print_invoice_dialog(page):
    # Implement print functionality
    pass

def confirm_delete_invoice(aufmass_nr, page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu_func):
    def delete_confirmed(e):
        delete_invoice(aufmass_nr, page)
        page.dialog.open = False
        page.update()
        # Aktualisieren Sie die Liste der Aufmaße
        show_edit_invoice_dialog(page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu_func)

    def cancel_delete(e):
        page.dialog.open = False
        page.update()
        # Zurück zur Übersicht der existierenden Aufmaße
        show_edit_invoice_dialog(page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu_func)

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Aufmaß Nr. {aufmass_nr} löschen?"),
        content=ft.Text("Möchten Sie dieses Aufmaß wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden."),
        actions=[
            ft.TextButton("Abbrechen", on_click=cancel_delete),
            ft.TextButton("Löschen", on_click=delete_confirmed),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.dialog = confirm_dialog
    confirm_dialog.open = True
    page.update()
