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

    def show_start_screen(e=None):
        page.clean()
        page.add(start_screen)
        page.update()

    def back_to_main_menu(e):
        show_start_screen()  # Rufen Sie die Funktion auf

    def show_aufmass_screen():
        def radio_changed(e):
            weiter_button.disabled = not e.control.value
            page.update()

        def weiter_clicked(e):
            selected_option = radio_group.value
            if selected_option == "hinzufugen":
                show_invoice_form()
            elif selected_option == "bearbeiten":
                # Hier Logik für "bearbeiten" einfügen
                pass
            elif selected_option == "berichte":
                # Hier Logik für "Berichte Anzeigen/Drucken" einfügen
                pass

        def show_invoice_form():
            page.clean()
            invoice_form = InvoiceForm(page)
            page.add(invoice_form)
            page.update()

        radio_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="hinzufugen", label="hinzufügen", fill_color=ft.colors.BLUE_500),
                ft.Radio(value="bearbeiten", label="bearbeiten", fill_color=ft.colors.BLUE_500),
                ft.Radio(value="berichte", label="Berichte Anzeigen/Drucken", fill_color=ft.colors.BLUE_500),
            ]),
            on_change=radio_changed
        )

        aufmass_screen = ft.Container(
            content=ft.Column([
                ft.Text("Aufmaß", size=28, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700),
                ft.Container(height=20),
                ft.Card(
                    content=ft.Container(
                        content=radio_group,
                        padding=20,
                    ),
                    elevation=5,
                ),
                ft.Container(height=20),
                ft.Row([
                    ft.OutlinedButton("zurück", on_click=lambda _: show_start_screen(), style=ft.ButtonStyle(color=ft.colors.BLUE_700)),
                    weiter_button := ft.ElevatedButton("weiter", on_click=weiter_clicked, disabled=True, style=ft.ButtonStyle(color=ft.colors.WHITE, bgcolor=ft.colors.BLUE_700)),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
            padding=40,
            bgcolor=ft.colors.WHITE,
        )
        page.clean()
        page.add(aufmass_screen)
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
