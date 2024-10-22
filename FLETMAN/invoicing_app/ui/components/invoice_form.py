import flet as ft
import os
from datetime import datetime
from ui.components.topbar import TopBar
from database.db_operations import get_db_connection
from .invoice_pdf_generator import generate_pdf
from .invoice_form_helpers import (
    load_items, get_dammdicke_options, get_base_price,
    get_material_price, get_taetigkeit_faktor, update_price, get_positionsnummer
)

class InvoiceForm(ft.UserControl):
    def __init__(self, page, aufmass_nr=None, is_preview=False, initial_color_scheme="BLUE", initial_theme_mode=ft.ThemeMode.LIGHT):
        super().__init__()
        self.page = page
        self.aufmass_nr = aufmass_nr
        self.is_preview = is_preview
        self.color_scheme = initial_color_scheme
        self.theme_mode = initial_theme_mode
        self.invoice_detail_fields = {}
        self.article_list_header = None
        self.article_summaries = []
        self.selected_sonderleistungen = []
        self.selected_zuschlaege = []
        self.pdf_generated = False
        self.next_aufmass_nr = self.get_next_aufmass_nr()

    def build(self):
        self.topbar = TopBar(self.page, self.open_settings, self.show_help, self.color_scheme)
        
        self.content = ft.Column([
            self.topbar,
            ft.Container(
                content=self.create_invoice_form(),
                expand=True,
                padding=20,
            )
        ], expand=True)

        return self.content

    def create_invoice_form(self):
        form = ft.ResponsiveRow([
            ft.Column([
                self.create_invoice_details(),
                self.create_article_input(),
                self.create_article_list(),
                self.create_total_section(),
            ], col={"sm": 12, "md": 8, "lg": 9}),
            ft.Column([
                self.create_action_buttons(),
            ], col={"sm": 12, "md": 4, "lg": 3}),
        ], expand=True)

        return form

    def create_invoice_details(self):
        self.invoice_detail_fields = {
            'client_name': ft.Dropdown(label="Kunde", on_change=self.toggle_new_entry),
            'bestell_nr': ft.Dropdown(label="Bestell-Nr.", on_change=self.toggle_new_entry),
            'bestelldatum': ft.TextField(label="Bestelldatum"),
            'baustelle': ft.Dropdown(label="Baustelle", on_change=self.toggle_new_entry),
            'anlagenteil': ft.Dropdown(label="Anlagenteil", on_change=self.toggle_new_entry),
            'aufmass_nr': ft.TextField(label="Aufmaß-Nr.", read_only=True, value=self.next_aufmass_nr),
            'auftrags_nr': ft.Dropdown(label="Auftrags-Nr.", on_change=self.toggle_new_entry),
            'ausfuehrungsbeginn': ft.TextField(label="Ausführungsbeginn"),
            'ausfuehrungsende': ft.TextField(label="Ausführungsende")
        }

        details = ft.ResponsiveRow([
            ft.Column([ft.Text("Rechnungsdetails", size=20, weight=ft.FontWeight.BOLD)], col=12),
            *[ft.Column([field], col={"sm": 12, "md": 6, "lg": 4}) for field in self.invoice_detail_fields.values()]
        ])

        return details

    def create_article_input(self):
        self.bauteil_dropdown = ft.Dropdown(label="Bauteil", on_change=self.update_price)
        self.dammdicke_dropdown = ft.Dropdown(label="Dämmdicke", on_change=self.update_price)
        self.taetigkeit_dropdown = ft.Dropdown(label="Tätigkeit", on_change=self.update_price)
        self.einheit_dropdown = ft.Dropdown(label="Einheit", on_change=self.update_price)
        self.menge_field = ft.TextField(label="Menge", on_change=self.update_price)
        self.preis_field = ft.TextField(label="Preis", read_only=True)

        input_fields = ft.ResponsiveRow([
            ft.Column([ft.Text("Artikel hinzufügen", size=20, weight=ft.FontWeight.BOLD)], col=12),
            ft.Column([self.bauteil_dropdown], col={"sm": 12, "md": 6, "lg": 4}),
            ft.Column([self.dammdicke_dropdown], col={"sm": 12, "md": 6, "lg": 4}),
            ft.Column([self.taetigkeit_dropdown], col={"sm": 12, "md": 6, "lg": 4}),
            ft.Column([self.einheit_dropdown], col={"sm": 12, "md": 6, "lg": 4}),
            ft.Column([self.menge_field], col={"sm": 12, "md": 6, "lg": 4}),
            ft.Column([self.preis_field], col={"sm": 12, "md": 6, "lg": 4}),
            ft.Column([ft.ElevatedButton("Artikel hinzufügen", on_click=self.add_article)], col=12),
        ])

        return input_fields

    def create_article_list(self):
        self.article_list_header = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Position")),
                ft.DataColumn(ft.Text("Bauteil")),
                ft.DataColumn(ft.Text("Dämmdicke")),
                ft.DataColumn(ft.Text("Tätigkeit")),
                ft.DataColumn(ft.Text("Einheit")),
                ft.DataColumn(ft.Text("Menge")),
                ft.DataColumn(ft.Text("Preis")),
                ft.DataColumn(ft.Text("Zwischensumme")),
                ft.DataColumn(ft.Text("Aktionen")),
            ],
            rows=[]
        )

        return ft.Column([
            ft.Text("Artikelliste", size=20, weight=ft.FontWeight.BOLD),
            self.article_list_header
        ])

    def create_total_section(self):
        self.total_price_text = ft.Text("Gesamtpreis: 0.00 €", size=20, weight=ft.FontWeight.BOLD)
        return ft.Column([self.total_price_text])

    def create_action_buttons(self):
        return ft.Column([
            ft.ElevatedButton("Speichern mit PDF", on_click=self.save_invoice_with_pdf),
            ft.ElevatedButton("Speichern ohne PDF", on_click=self.save_invoice_without_pdf),
            ft.ElevatedButton("Neues Aufmaß", on_click=self.reset_form),
            ft.ElevatedButton("Zuschläge", on_click=self.show_zuschlaege_dialog),
            ft.ElevatedButton("Sonderleistungen", on_click=self.show_sonderleistungen_dialog),
        ])

    def open_settings(self, e):
        color_options = [
            ft.dropdown.Option("BLUE"),
            ft.dropdown.Option("GREEN"),
            ft.dropdown.Option("RED"),
            ft.dropdown.Option("PURPLE"),
            ft.dropdown.Option("ORANGE")
        ]
        
        color_dropdown = ft.Dropdown(
            label="Farbschema",
            options=color_options,
            value=self.color_scheme,
            on_change=self.change_color_scheme
        )

        theme_switch = ft.Switch(
            label="Dunkles Theme",
            value=self.theme_mode == ft.ThemeMode.DARK,
            on_change=self.toggle_theme
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text("Einstellungen"),
            content=ft.Column([color_dropdown, theme_switch], tight=True),
            actions=[
                ft.TextButton("Schließen", on_click=lambda _: self.close_dialog())
            ],
        )
        
        self.show_dialog(dialog)

    def show_help(self, e):
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
                ft.TextButton("Schließen", on_click=lambda _: self.close_dialog())
            ],
        )
        
        self.show_dialog(dialog)

    def update_theme(self):
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=getattr(ft.colors, self.color_scheme),
                on_primary=ft.colors.WHITE,
            )
        )
        self.page.theme_mode = self.theme_mode
        self.page.update()

    def update_topbar(self):
        aufmass_nr = self.invoice_detail_fields['aufmass_nr'].value if 'aufmass_nr' in self.invoice_detail_fields else "Neu"
        self.topbar.update_title(f"Aufmaß Nr. {aufmass_nr}")

    def save_invoice_with_pdf(self, e):
        invoice_data = self.get_invoice_data()
        self.save_invoice_to_db(invoice_data)
        generate_pdf(invoice_data, include_prices=True)
        self.show_snack_bar("Rechnung mit PDF gespeichert")

    def save_invoice_without_pdf(self, e):
        invoice_data = self.get_invoice_data()
        self.save_invoice_to_db(invoice_data)
        self.show_snack_bar("Rechnung ohne PDF gespeichert")

    def reset_form(self, e):
        for field in self.invoice_detail_fields.values():
            if not isinstance(field, ft.TextField) or not field.read_only:
                field.value = None
        self.invoice_detail_fields['aufmass_nr'].value = self.get_next_aufmass_nr()
        self.article_list_header.rows.clear()
        self.article_summaries.clear()
        self.selected_sonderleistungen.clear()
        self.selected_zuschlaege.clear()
        self.update_total_price()
        self.update()
        self.show_snack_bar("Formular zurückgesetzt")

    def show_zuschlaege_dialog(self, e):
        # Implementieren Sie hier den Dialog für Zuschläge
        pass

    def show_sonderleistungen_dialog(self, e):
        # Implementieren Sie hier den Dialog für Sonderleistungen
        pass

    def toggle_new_entry(self, e):
        field_name = e.control.data
        if e.control.value == "Neu":
            self.new_entry_fields[field_name].visible = True
        else:
            self.new_entry_fields[field_name].visible = False
        self.update()

    def update_price(self, e=None):
        bauteil = self.bauteil_dropdown.value
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        einheit = self.einheit_dropdown.value
        menge = self.menge_field.value

        if all([bauteil, dammdicke, taetigkeit, einheit, menge]):
            base_price = get_base_price(bauteil, dammdicke)
            material_price = get_material_price(bauteil, dammdicke)
            taetigkeit_faktor = get_taetigkeit_faktor(taetigkeit)
            
            price = (base_price + material_price) * taetigkeit_faktor * float(menge)
            self.preis_field.value = f"{price:.2f}"
        else:
            self.preis_field.value = ""
        
        self.update()

    def add_article(self, e):
        bauteil = self.bauteil_dropdown.value
        dammdicke = self.dammdicke_dropdown.value
        taetigkeit = self.taetigkeit_dropdown.value
        einheit = self.einheit_dropdown.value
        menge = self.menge_field.value
        preis = self.preis_field.value

        if all([bauteil, dammdicke, taetigkeit, einheit, menge, preis]):
            position = get_positionsnummer(bauteil, dammdicke, taetigkeit)
            zwischensumme = float(preis) * float(menge)
            
            new_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(position)),
                    ft.DataCell(ft.Text(bauteil)),
                    ft.DataCell(ft.Text(dammdicke)),
                    ft.DataCell(ft.Text(taetigkeit)),
                    ft.DataCell(ft.Text(einheit)),
                    ft.DataCell(ft.Text(menge)),
                    ft.DataCell(ft.Text(preis)),
                    ft.DataCell(ft.Text(f"{zwischensumme:.2f}")),
                    ft.DataCell(
                        ft.IconButton(
                            ft.icons.DELETE,
                            on_click=lambda _: self.delete_article(new_row)
                        )
                    ),
                ]
            )
            
            self.article_list_header.rows.append(new_row)
            self.article_summaries.append({
                'zwischensumme': zwischensumme,
                'sonderleistungen': []
            })
            
            self.clear_input_fields()
            self.update_total_price()
            self.update()
        else:
            self.show_snack_bar("Bitte füllen Sie alle Felder aus")

    def delete_article(self, row):
        index = self.article_list_header.rows.index(row)
        self.article_list_header.rows.remove(row)
        del self.article_summaries[index]
        self.update_total_price()
        self.update()

    def clear_input_fields(self):
        self.bauteil_dropdown.value = None
        self.dammdicke_dropdown.value = None
        self.taetigkeit_dropdown.value = None
        self.einheit_dropdown.value = None
        self.menge_field.value = ""
        self.preis_field.value = ""

    def update_total_price(self):
        total = sum(summary['zwischensumme'] for summary in self.article_summaries)
        for zuschlag in self.selected_zuschlaege:
            total *= (1 + zuschlag[1])
        self.total_price_text.value = f"Gesamtpreis: {total:.2f} €"
        self.update()

    def get_invoice_data(self):
        return {
            'client_name': self.invoice_detail_fields['client_name'].value,
            'bestell_nr': self.invoice_detail_fields['bestell_nr'].value,
            'bestelldatum': self.invoice_detail_fields['bestelldatum'].value,
            'baustelle': self.invoice_detail_fields['baustelle'].value,
            'anlagenteil': self.invoice_detail_fields['anlagenteil'].value,
            'aufmass_nr': self.invoice_detail_fields['aufmass_nr'].value,
            'auftrags_nr': self.invoice_detail_fields['auftrags_nr'].value,
            'ausfuehrungsbeginn': self.invoice_detail_fields['ausfuehrungsbeginn'].value,
            'ausfuehrungsende': self.invoice_detail_fields['ausfuehrungsende'].value,
            'articles': [
                {
                    'position': row.cells[0].content.value,
                    'bauteil': row.cells[1].content.value,
                    'dammdicke': row.cells[2].content.value,
                    'taetigkeit': row.cells[3].content.value,
                    'einheit': row.cells[4].content.value,
                    'menge': row.cells[5].content.value,
                    'preis': row.cells[6].content.value,
                    'zwischensumme': row.cells[7].content.value,
                }
                for row in self.article_list_header.rows
            ],
            'zuschlaege': self.selected_zuschlaege,
            'sonderleistungen': self.selected_sonderleistungen,
            'total_price': float(self.total_price_text.value.split(":")[1].strip().replace("€", ""))
        }

    def save_invoice_to_db(self, invoice_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO invoice (
                    client_name, bestell_nr, bestelldatum, baustelle, anlagenteil,
                    aufmass_nr, auftrags_nr, ausfuehrungsbeginn, ausfuehrungsende,
                    zuschlaege, total_amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data['client_name'], invoice_data['bestell_nr'],
                invoice_data['bestelldatum'], invoice_data['baustelle'],
                invoice_data['anlagenteil'], invoice_data['aufmass_nr'],
                invoice_data['auftrags_nr'], invoice_data['ausfuehrungsbeginn'],
                invoice_data['ausfuehrungsende'],
                ','.join(f"{z[0]}:{z[1]}" for z in invoice_data['zuschlaege']),
                invoice_data['total_price']
            ))
            
            invoice_id = cursor.lastrowid
            
            for article in invoice_data['articles']:
                cursor.execute('''
                    INSERT INTO invoice_items (
                        invoice_id, position, bauteil, dammdicke, taetigkeit,
                        einheit, menge, preis, zwischensumme
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    invoice_id, article['position'], article['bauteil'],
                    article['dammdicke'], article['taetigkeit'], article['einheit'],
                    article['menge'], article['preis'], article['zwischensumme']
                ))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_next_aufmass_nr(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(CAST(aufmass_nr AS INTEGER)) FROM invoice")
            max_nr = cursor.fetchone()[0]
            return str(int(max_nr) + 1) if max_nr else "1"
        finally:
            cursor.close()
            conn.close()

    def show_dialog(self, dialog):
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def close_dialog(self):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def show_snack_bar(self, text):
        self.page.snack_bar = ft.SnackBar(ft.Text(text))
        self.page.snack_bar.open = True
        self.page.update()

    def change_color_scheme(self, e):
        self.color_scheme = e.control.value
        self.update_theme()

    def toggle_theme(self, e):
        self.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self.update_theme()
