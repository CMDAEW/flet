import flet as ft
from ui.components.invoice_form import InvoiceForm
from ui.components.edit_invoice import show_edit_invoice_dialog
from database.db_init import initialize_database
import logging
import os

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

    def add_logo_and_topbar():
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logos", "KAE_Logo_RGB_300dpi2.jpg")
        if os.path.exists(logo_path):
            logo = ft.Image(src=logo_path, width=100, height=40, fit=ft.ImageFit.CONTAIN)
        else:
            logo = ft.Text("KAEFER")  # Fallback, wenn das Logo nicht gefunden wird
            logging.warning(f"Logo-Datei nicht gefunden: {logo_path}")

        page.appbar = ft.AppBar(
            leading=logo,
            leading_width=100,
            title=ft.Text(""),  # Leerer Text anstelle des Titels
            center_title=False,
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                ft.IconButton(ft.icons.SETTINGS, on_click=open_settings),
                ft.IconButton(ft.icons.HELP_OUTLINE, on_click=show_help),
            ],
        )
        page.update()

    def open_settings(e):
        color_options = [
            ft.dropdown.Option("BLUE"),
            ft.dropdown.Option("GREEN"),
            ft.dropdown.Option("RED"),
            ft.dropdown.Option("PURPLE"),
            ft.dropdown.Option("ORANGE")
        ]
        
        current_color = get_color_scheme()
        
        color_dropdown = ft.Dropdown(
            label="Farbschema",
            options=color_options,
            value=current_color,
            on_change=change_color_scheme
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text("Einstellungen"),
            content=ft.Column([color_dropdown], tight=True),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: close_dialog())
            ],
        )
        
        show_dialog(dialog)

    def change_color_scheme(e):
        color = e.control.value
        set_color_scheme(color)
        page.theme = ft.Theme(color_scheme=ft.ColorScheme(
            primary=getattr(ft.colors, color),
            on_primary=ft.colors.WHITE,
        ))
        page.update()

    def get_color_scheme():
        if hasattr(page, 'client_storage'):
            color = page.client_storage.get("color_scheme")
            return color if color else "BLUE"
        return "BLUE"  # Default color if client_storage is not available

    def set_color_scheme(color):
        if hasattr(page, 'client_storage'):
            page.client_storage.set("color_scheme", color)

    def show_help(e):
        help_text = """
        Hilfe zur Rechnungs-App:

        1. Kopfdaten ausfüllen: Füllen Sie alle erforderlichen Felder im oberen Bereich aus.
        2. Artikel hinzufügen: Wählen Sie Bauteil, Dämmdicke, etc. und klicken Sie auf 'Artikel hinzufügen'.
        3. Artikel bearbeiten: Klicken Sie auf einen Artikel in der Liste, um ihn zu bearbeiten.
        4. Artikel löschen: Klicken Sie auf das Mülleimer-Symbol neben einem Artikel, um ihn zu löschen.
        5. Sonderleistungen: Klicken Sie auf 'Sonderleistungen', um zusätzliche Leistungen hinzuzufügen.
        6. Zuschläge: Klicken Sie auf 'Zuschläge', um Zuschläge hinzuzufügen.
        7. PDF erstellen: Klicken Sie auf 'PDF mit Preisen erstellen' oder 'PDF ohne Preise erstellen'.
        8. Neues Aufmaß: Klicken Sie auf 'Speichern und neues Aufmaß erstellen', um ein neues Aufmaß zu beginnen.

        Bei weiteren Fragen wenden Sie sich bitte an den Support.
        """
        
        dialog = ft.AlertDialog(
            title=ft.Text("Hilfe"),
            content=ft.Text(help_text),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: close_dialog())
            ],
        )
        
        show_dialog(dialog)

    def show_dialog(dialog):
        page.dialog = dialog
        dialog.open = True
        page.update()

    def close_dialog():
        if page.dialog:
            page.dialog.open = False
            page.update()

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
        if hasattr(page, 'dialog'):
            page.dialog.open = False
        content_column.controls.clear()
        content_column.controls.append(create_start_screen())
        page.update()

    def show_aufmass_screen():
        def aufmass_button_clicked(e):
            if e.control.text == "hinzufügen":
                show_invoice_form()
            elif e.control.text == "bearbeiten":
                show_edit_invoice_dialog(page, on_invoice_selected, on_invoice_preview, on_pdf_with_prices, on_pdf_without_prices, back_to_main_menu)
            elif e.control.text == "Berichte Anzeigen/Drucken":
                # Implement logic for reports
                pass

        def on_invoice_preview(aufmass_nr):
            invoice_form = InvoiceForm(page, aufmass_nr, is_preview=True)
            content_column.controls.clear()
            content_column.controls.append(ft.Container(content=invoice_form, expand=True))
            page.update()

        def close_preview():
            content_column.controls.clear()
            show_aufmass_screen()
            page.update()

        def on_pdf_with_prices(aufmass_nr):
            invoice_form = InvoiceForm(page, aufmass_nr)
            invoice_form.create_pdf(include_prices=True, force_new=True)

        def on_pdf_without_prices(aufmass_nr):
            invoice_form = InvoiceForm(page, aufmass_nr)
            invoice_form.create_pdf(include_prices=False, force_new=True)

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
        invoice_form = InvoiceForm(page, aufmass_nr, is_preview=False)
        page.invoice_form = invoice_form
        
        if aufmass_nr is None:
            invoice_form.save_invoice_with_pdf_button.visible = False
            invoice_form.save_invoice_without_pdf_button.visible = False
            invoice_form.new_aufmass_button.visible = False
        
        content_column.controls.append(ft.Container(content=invoice_form, expand=True))
        page.update()
        invoice_form.enable_all_inputs()
        invoice_form.update_topbar()
        page.update()

    def on_invoice_selected(aufmass_nr):
        show_invoice_form(aufmass_nr)
        page.invoice_form.update_topbar()
        page.update()

    page.add(main_container)
    page.go = show_start_screen

    # Add the TopBar
    add_logo_and_topbar()

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
