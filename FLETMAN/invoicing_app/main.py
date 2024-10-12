import flet as ft
from ui.components.invoice_form import InvoiceForm
from database.db_init import initialize_database
import logging

# Konfigurieren Sie das Logging
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

    # Zoom-Steuerung
    zoom_level = 1.0

    def zoom_in(e):
        nonlocal zoom_level
        zoom_level = min(2.0, zoom_level + 0.1)
        update_zoom()

    def zoom_out(e):
        nonlocal zoom_level
        zoom_level = max(0.5, zoom_level - 0.1)
        update_zoom()

    def update_zoom():
        content_column.scale = zoom_level
        page.update()

    zoom_controls = ft.Row([
        ft.IconButton(ft.icons.ZOOM_IN, on_click=zoom_in),
        ft.IconButton(ft.icons.ZOOM_OUT, on_click=zoom_out),
    ], alignment=ft.MainAxisAlignment.END)

    # Scrollbarer Inhaltsbereich
    content_column = ft.Column([], expand=True, scroll=ft.ScrollMode.ALWAYS)

    # Hauptcontainer
    main_container = ft.Container(
        content=ft.Column([
            zoom_controls,
            content_column
        ], expand=True),
        expand=True,
    )

    def show_start_screen(e=None):
        content_column.controls.clear()
        content_column.controls.append(start_screen)
        page.update()

    def back_to_main_menu(e):
        show_start_screen()

    def show_aufmass_screen():
        def button_clicked(e):
            if e.control.text == "hinzufügen":
                show_invoice_form()
            elif e.control.text == "bearbeiten":
                # Hier Logik für das Bearbeiten einfügen
                pass
            elif e.control.text == "Berichte Anzeigen/Drucken":
                # Hier Logik für Berichte einfügen
                pass

        def show_invoice_form():
            content_column.controls.clear()
            invoice_form = InvoiceForm(page)
            content_column.controls.append(ft.Container(content=invoice_form, expand=True))
            page.update()

        aufmass_screen = ft.Container(
            content=ft.Column([
                ft.Text("Aufmaß", size=28, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700),
                ft.Container(height=50),
                ft.ElevatedButton("hinzufügen", on_click=button_clicked, width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ft.Container(height=20),
                ft.ElevatedButton("bearbeiten", on_click=button_clicked, width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ft.Container(height=20),
                ft.ElevatedButton("Berichte Anzeigen/Drucken", on_click=button_clicked, width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ft.Container(height=50),
                ft.ElevatedButton("zurück", on_click=lambda _: show_start_screen(), width=250, height=60,
                                  style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=40,
            bgcolor=ft.colors.WHITE,
            alignment=ft.alignment.center,
        )
        content_column.controls.clear()
        content_column.controls.append(aufmass_screen)
        page.update()

    def button_clicked(e):
        if e.control.text == "Aufmaß":
            show_aufmass_screen()
        elif e.control.text == "Arbeitsbescheinigung":
            # Hier Logik für Arbeitsbescheinigung einfügen
            pass
        elif e.control.text == "Verwaltung":
            # Hier Logik für Verwaltung einfügen
            pass

    start_screen = ft.Container(
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
    )

    page.add(main_container)
    page.go = show_start_screen  # Setzen Sie die Standardroute '/' auf show_start_screen

    show_start_screen()  # Zeigen Sie den Startbildschirm initial an

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
