import flet as ft
from ui.components.invoice_form import InvoiceForm
from ui.components.edit_invoice import show_edit_invoice_dialog
from database.db_init import initialize_database
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(page: ft.Page):
    page.title = "KAEFER Industrie GmbH Abrechnungsprogramm"
    page.window_width = 1200
    page.window_height = 800
    page.window_resizable = True
    page.window_maximized = True
    page.bgcolor = ft.colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0

    # Scrollable content area
    content_column = ft.Column([], expand=True, scroll=ft.ScrollMode.AUTO)

    def button_clicked(e):
        if e.control.text == "Aufmaß":
            show_aufmass_screen()
        elif e.control.text == "Arbeitsbescheinigung":
            # Implement logic for "Arbeitsbescheinigung"
            pass
        elif e.control.text == "Verwaltung":
            # Implement logic for "Verwaltung"
            pass

    def create_start_screen():
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Willkommen beim KAEFER Industrie GmbH Abrechnungsprogramm", 
                            size=28, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700),
                    ft.Container(height=50),
                    ft.ElevatedButton("Aufmaß", on_click=button_clicked, width=250, height=60,
                                      style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                    ft.Container(height=20),
                    ft.ElevatedButton("Arbeitsbescheinigung", on_click=button_clicked, width=250, height=60,
                                      style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                    ft.Container(height=20),
                    ft.ElevatedButton("Verwaltung", on_click=button_clicked, width=250, height=60,
                                      style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=40,
            bgcolor=ft.colors.WHITE,
            expand=True,
        )

    # Main container
    main_container = ft.Container(
        content=content_column,
        expand=True,
        padding=20,
    )

    def show_start_screen(e=None):
        content_column.controls.clear()
        content_column.controls.append(create_start_screen())
        page.update()

    def back_to_main_menu(e=None):
        show_start_screen()

    def show_aufmass_screen():
        def aufmass_button_clicked(e):
            if e.control.text == "hinzufügen":
                show_invoice_form()
            elif e.control.text == "bearbeiten":
                show_edit_invoice_dialog(page, on_invoice_selected, on_invoice_preview)
            elif e.control.text == "Berichte Anzeigen/Drucken":
                # Implement logic for reports
                pass

        def on_invoice_preview(aufmass_nr):
            invoice_form = InvoiceForm(page, aufmass_nr, is_preview=True)
            content_column.controls.clear()
            content_column.controls.append(ft.Container(content=invoice_form, expand=True, opacity=0.7))
            page.update()

        aufmass_screen = ft.Container(
            content=ft.Column([
                ft.Text("Aufmaß", size=28, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700),
                ft.Container(height=50),
                ft.ElevatedButton("hinzufügen", on_click=aufmass_button_clicked, width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ft.Container(height=20),
                ft.ElevatedButton("bearbeiten", on_click=aufmass_button_clicked, width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ft.Container(height=20),
                ft.ElevatedButton("Berichte Anzeigen/Drucken", on_click=aufmass_button_clicked, width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ft.Container(height=50),
                ft.ElevatedButton("zurück", on_click=lambda _: show_start_screen(), width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=40,
            bgcolor=ft.colors.WHITE,
            expand=True,
        )
        content_column.controls.clear()
        content_column.controls.append(aufmass_screen)
        page.update()

    def show_invoice_form(aufmass_nr=None):
        content_column.controls.clear()
        invoice_form = InvoiceForm(page, aufmass_nr)
        content_column.controls.append(ft.Container(content=invoice_form, expand=True))
        page.update()

    def on_invoice_selected(aufmass_nr):
        show_invoice_form(aufmass_nr)

    page.add(main_container)
    page.go = show_start_screen

    show_start_screen()

if __name__ == "__main__":
    try:
        logging.info("Initialisiere die Datenbank...")
        initialize_database()
        logging.info("Datenbankinitialisierung abgeschlossen.")
        
        logging.info("Starte die Flet-Anwendung...")
        ft.app(target=main)
    except Exception as e:
        logging.error(f"Ein Fehler ist aufgetreten: {e}")
        raise
