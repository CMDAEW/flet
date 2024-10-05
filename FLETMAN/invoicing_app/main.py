import flet as ft
from ui.components.invoice_form import InvoiceForm
from database.db_init import initialize_database
import logging

# Konfigurieren Sie das Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(page: ft.Page):
    page.title = "KAEFER Industrie GmbH Abrechnungsprogramm"
    
    # Setzen Sie eine angemessene Fenstergröße
    page.window_width = 1200
    page.window_height = 800
    page.window_resizable = True
    page.window_maximized = True  # Startet die Anwendung maximiert

    # Setzen Sie einen hellen Hintergrund
    page.bgcolor = ft.colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT

    # Erstellen Sie das InvoiceForm-Objekt
    invoice_form = InvoiceForm(page)

    # Fügen Sie das InvoiceForm zum Seitenlayout hinzu
    page.add(invoice_form)

    page.update()

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
