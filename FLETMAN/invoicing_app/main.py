import flet as ft
from ui.components.topbar import TopBar
from ui.components.invoice_form import InvoiceForm
from ui.components.edit_invoice import show_edit_invoice_dialog

def main(page: ft.Page):
    page.title = "KAEFER Industrie GmbH Abrechnungsprogramm"
    page.window.maximized = True
    page.padding = 0
    page.spacing = 0

    def open_settings(e):
        print("Einstellungen öffnen")
        # TODO: Implementieren Sie hier die Einstellungsfunktion

    def show_help(e):
        print("Hilfe anzeigen")
        # TODO: Implementieren Sie hier die Hilfefunktion

    topbar = TopBar(page, open_settings, show_help, "BLUE")

    content_column = ft.Column(expand=True)

    def show_start_screen(e=None):
        content_column.controls.clear()
        start_screen = ft.Column([
            ft.Text("Willkommen beim KAEFER Industrie GmbH Abrechnungsprogramm", size=24, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("Aufmaß", on_click=show_aufmass_screen),
            ft.ElevatedButton("Einstellungen", on_click=open_settings),
            ft.ElevatedButton("Hilfe", on_click=show_help),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        content_column.controls.append(start_screen)
        topbar.update_title("KAEFER Industrie GmbH")
        page.update()

    def show_aufmass_screen(e=None):
        content_column.controls.clear()
        aufmass_screen = ft.Column([
            ft.Text("Aufmaß", size=28, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("Neues Aufmaß", on_click=lambda _: show_invoice_form()),
            ft.ElevatedButton("Aufmaß bearbeiten", on_click=lambda _: show_edit_invoice_dialog(page, on_invoice_selected)),
            ft.ElevatedButton("Zurück zum Hauptmenü", on_click=show_start_screen),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        content_column.controls.append(aufmass_screen)
        topbar.update_title("Aufmaß")
        page.update()

    def show_invoice_form(aufmass_nr=None):
        content_column.controls.clear()
        invoice_form = InvoiceForm(page, aufmass_nr, is_preview=False, 
                                   initial_color_scheme="BLUE", 
                                   initial_theme_mode=ft.ThemeMode.LIGHT)
        content_column.controls.append(invoice_form)
        topbar.update_title(f"Aufmaß Nr. {aufmass_nr}" if aufmass_nr else "Neues Aufmaß")
        page.update()

    def on_invoice_selected(aufmass_nr):
        show_invoice_form(aufmass_nr)

    main_container = ft.Container(
        content=ft.Column([topbar, content_column]),
        expand=True,
    )

    page.add(main_container)
    show_start_screen()

    page.update()

ft.app(target=main)
