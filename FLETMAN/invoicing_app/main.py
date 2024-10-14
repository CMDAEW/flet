import flet as ft
from ui.components.invoice_form import InvoiceForm
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

    # Zoom controls
    zoom_level = 1.0
    zoom_step = 0.1
    max_zoom = 2.0
    min_zoom = 0.5

    def zoom_in(e):
        nonlocal zoom_level
        zoom_level = min(max_zoom, zoom_level + zoom_step)
        update_zoom()

    def zoom_out(e):
        nonlocal zoom_level
        zoom_level = max(min_zoom, zoom_level - zoom_step)
        update_zoom()

    def reset_zoom(e):
        nonlocal zoom_level
        zoom_level = 1.0
        update_zoom()

    def update_zoom():
        # Apply scaling to the main container
        main_container.scale = zoom_level
        zoom_text.value = f"{zoom_level:.1f}x"
        page.update()

    zoom_text = ft.Text(f"{zoom_level:.1f}x")
    zoom_controls = ft.Row([
        ft.IconButton(ft.icons.ZOOM_OUT, on_click=zoom_out),
        zoom_text,
        ft.IconButton(ft.icons.ZOOM_IN, on_click=zoom_in),
        ft.IconButton(ft.icons.RESTART_ALT, on_click=reset_zoom, tooltip="Zoom zurücksetzen"),
    ], alignment=ft.MainAxisAlignment.END)

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
        content=ft.Column([
            ft.Container(
                content=zoom_controls,
                padding=10,
                bgcolor=ft.colors.WHITE,
            ),
            ft.Container(
                content=content_column,
                expand=True,
                padding=20,
            )
        ], expand=True),
        expand=True,
        clip_behavior=ft.ClipBehavior.NONE  # Ensure the container doesn't clip content
    )

    def show_start_screen(e=None):
        content_column.controls.clear()
        content_column.controls.append(create_start_screen())
        page.update()

    def show_aufmass_screen():
        def aufmass_button_clicked(e):
            if e.control.text == "hinzufügen":
                show_invoice_form()
            elif e.control.text == "bearbeiten":
                # Implement logic for editing
                pass
            elif e.control.text == "Berichte Anzeigen/Drucken":
                # Implement logic for reports
                pass

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

    def show_invoice_form():
        content_column.controls.clear()
        invoice_form = InvoiceForm(page)
        content_column.controls.append(ft.Container(content=invoice_form, expand=True))
        page.update()

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
