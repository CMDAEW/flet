import flet as ft
from ui import InvoicingApp
from database.db_init import initialize_database

def main(page: ft.Page):
    app = InvoicingApp(page)
    page.add(app)

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)
