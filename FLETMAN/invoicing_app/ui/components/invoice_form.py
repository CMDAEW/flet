import flet as ft
from database.db_operations import save_invoice_to_db, get_unique_client_names

class InvoiceForm(ft.UserControl):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.initialize_ui_elements()

    def initialize_ui_elements(self):
        self.client_name_dropdown = ft.Dropdown(label="Kundenname", width=300)
        self.client_name_entry = ft.TextField(label="Neuer Kundenname", visible=False)
        self.bestell_nr = ft.TextField(label="Bestell-Nr.", width=200)
        self.bestelldatum = ft.TextField(label="Bestelldatum", width=200)
        self.baustelle = ft.TextField(label="Baustelle", width=200)
        self.anlagenteil = ft.TextField(label="Anlagenteil", width=200)
        self.aufmass_nr = ft.TextField(label="Aufmaß-Nr.", width=200)
        self.aufmassart = ft.Dropdown(
            label="Aufmaßart",
            width=200,
            options=[
                ft.dropdown.Option("Aufmaß"),
                ft.dropdown.Option("Abschlagsrechnung"),
                ft.dropdown.Option("Schlussrechnung")
            ]
        )
        self.auftrags_nr = ft.TextField(label="Auftrags-Nr.", width=200)
        self.ausfuehrungsbeginn = ft.TextField(label="Ausführungsbeginn", width=200)
        self.ausfuehrungsende = ft.TextField(label="Ausführungsende", width=200)

    def build(self):
        return ft.Column([
            ft.Row([self.client_name_dropdown, self.client_name_entry]),
            ft.Row([self.bestell_nr, self.bestelldatum, self.baustelle]),
            ft.Row([self.anlagenteil, self.aufmass_nr, self.aufmassart]),
            ft.Row([self.auftrags_nr, self.ausfuehrungsbeginn, self.ausfuehrungsende]),
        ])

    def save_invoice(self):
        if not self.client_name_dropdown.value or not self.parent.items:
            self.parent.show_snackbar("Bitte füllen Sie alle erforderlichen Felder aus.")
            return
        
        invoice_data = self.collect_invoice_data()
        if save_invoice_to_db(invoice_data, self.parent.conn):
            self.parent.show_snackbar("Rechnung erfolgreich gespeichert.")
            self.reset_form()
        else:
            self.parent.show_snackbar("Fehler beim Speichern der Rechnung.")

    def generate_pdf(self):
        if not self.client_name_dropdown.value or not self.parent.items:
            self.parent.show_snackbar("Bitte füllen Sie alle erforderlichen Felder aus und fügen Sie mindestens einen Artikel hinzu.")
            return
        
        invoice_data = self.collect_invoice_data()
        pdf_path = self.pdf_generieren(invoice_data)
        self.parent.show_snackbar(f"PDF wurde generiert: {pdf_path}")

    def collect_invoice_data(self):
        return {
            "client_name": self.client_name_dropdown.value,
            "bestell_nr": self.bestell_nr.value,
            "bestelldatum": self.bestelldatum.value,
            "baustelle": self.baustelle.value,
            "anlagenteil": self.anlagenteil.value,
            "aufmass_nr": self.aufmass_nr.value,
            "aufmassart": self.aufmassart.value,
            "auftrags_nr": self.auftrags_nr.value,
            "ausfuehrungsbeginn": self.ausfuehrungsbeginn.value,
            "ausfuehrungsende": self.ausfuehrungsende.value,
            "total": self.parent.invoice_table.calculate_total(),
            "items": self.parent.items
        }

    def reset_form(self):
        # Implement logic to reset the form
        pass

    def pdf_generieren(self, invoice_data):
        # Implement logic to generate PDF
        pass

    def update_client_names(self):
        client_names = get_unique_client_names(self.parent.conn)
        self.client_name_dropdown.options = [ft.dropdown.Option("Neuer Kunde")] + [ft.dropdown.Option(name) for name in client_names]
        self.client_name_dropdown.update()
