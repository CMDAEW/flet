import flet as ft
from database.db_operations import get_db_connection
import logging

class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.create_ui_elements()
        self.load_data()

    def create_ui_elements(self):
        # Rechnungsdetails Felder
        self.invoice_detail_fields = {
            'client_name': ft.Dropdown(label="Kunde", width=200),
            'bestell_nr': ft.Dropdown(label="Bestell-Nr.", width=200),
            'bestelldatum': ft.Dropdown(label="Bestelldatum", width=200),
            'baustelle': ft.Dropdown(label="Baustelle", width=200),
            'anlagenteil': ft.Dropdown(label="Anlagenteil", width=200),
            'aufmass_nr': ft.Dropdown(label="Aufmaß-Nr.", width=200),
            'auftrags_nr': ft.Dropdown(label="Auftrags-Nr.", width=200),
            'ausfuehrungsbeginn': ft.Dropdown(label="Ausführungsbeginn", width=200),
            'ausfuehrungsende': ft.Dropdown(label="Ausführungsende", width=200),
        }
        
        for field in self.invoice_detail_fields.values():
            field.on_change = self.on_dropdown_change

        self.new_entry_fields = {key: ft.TextField(label=f"Neuer {value.label}", visible=False, width=200) for key, value in self.invoice_detail_fields.items()}

        # Rechnungspositionen Felder
        self.position_fields = {
            'Bauteil': ft.Dropdown(label="Bauteil", width=200, on_change=self.on_bauteil_change),
            'DN': ft.Dropdown(label="DN", width=80, on_change=self.on_dn_change),
            'DA': ft.Dropdown(label="DA", width=80, on_change=self.on_da_change),
            'Size': ft.Dropdown(label="Dämmdicke", width=100),
            'Unit': ft.TextField(label="Mengeneinheit", width=100, read_only=True),
        }
        
        self.position_text_fields = {
            'Value': ft.TextField(label="Preis", width=100),
            'quantity': ft.TextField(label="Menge", width=100),
            'zwischensumme': ft.TextField(label="Zwischensumme", width=150, read_only=True),
        }

        # Button für Sonderleistungen
        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.show_sonderleistungen)

        # Button zum Hinzufügen der Position
        self.add_position_button = ft.ElevatedButton("Hinzufügen", on_click=self.add_position)

    def build(self):
        form_layout = ft.Column([
            ft.Text("Rechnungsangaben", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(height=20),
            ft.ResponsiveRow([
                ft.Column([
                    self.invoice_detail_fields['client_name'],
                    self.new_entry_fields['client_name'],
                    self.invoice_detail_fields['bestell_nr'],
                    self.new_entry_fields['bestell_nr'],
                    self.invoice_detail_fields['bestelldatum'],
                    self.new_entry_fields['bestelldatum'],
                ], col={"sm": 12, "md": 4}),
                ft.Column([
                    self.invoice_detail_fields['baustelle'],
                    self.new_entry_fields['baustelle'],
                    self.invoice_detail_fields['anlagenteil'],
                    self.new_entry_fields['anlagenteil'],
                    self.invoice_detail_fields['aufmass_nr'],
                    self.new_entry_fields['aufmass_nr'],
                ], col={"sm": 12, "md": 4}),
                ft.Column([
                    self.invoice_detail_fields['auftrags_nr'],
                    self.new_entry_fields['auftrags_nr'],
                    self.invoice_detail_fields['ausfuehrungsbeginn'],
                    self.new_entry_fields['ausfuehrungsbeginn'],
                    self.invoice_detail_fields['ausfuehrungsende'],
                    self.new_entry_fields['ausfuehrungsende'],
                ], col={"sm": 12, "md": 4}),
            ]),
        ])

        position_layout = ft.Row([
            self.position_fields['Bauteil'],
            self.position_fields['DN'],
            self.position_fields['DA'],
            self.position_fields['Size'],
            self.position_fields['Unit'],
            self.position_text_fields['Value'],
            self.position_text_fields['quantity'],
            self.position_text_fields['zwischensumme'],
            self.sonderleistungen_button,
            self.add_position_button,
        ], wrap=True, alignment=ft.MainAxisAlignment.START)

        form_layout.controls.extend([
            ft.Container(height=20),
            ft.Text("Rechnungspositionen", size=20, weight=ft.FontWeight.BOLD),
            position_layout,
        ])

        return ft.Container(
            content=form_layout,
            padding=20,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10,
        )

    def load_data(self):
        self.load_invoice_options()
        self.load_position_options()

    def load_invoice_options(self):
        for field_name in self.invoice_detail_fields:
            self.load_options_for_field(field_name)

    def load_position_options(self):
        self.load_bauteil_options()
        for field_name, dropdown in self.position_fields.items():
            if field_name != 'Bauteil':
                self.load_options_for_position_field(field_name)

    def load_options_for_field(self, field_name):
        cursor = self.conn.cursor()
        try:
            cursor.execute(f'SELECT DISTINCT {field_name} FROM invoice ORDER BY {field_name}')
            options = [row[0] for row in cursor.fetchall() if row[0]]
            self.invoice_detail_fields[field_name].options = [ft.dropdown.Option(option) for option in options]
            self.invoice_detail_fields[field_name].options.append(ft.dropdown.Option("Neuer Eintrag"))
        except Exception as e:
            logging.error(f"Fehler beim Laden der Optionen für {field_name}: {e}")
        finally:
            cursor.close()

    def load_bauteil_options(self):
        cursor = self.conn.cursor()
        try:
            # Rohrleitung
            cursor.execute("SELECT DISTINCT Bauteil FROM price_list WHERE Bauteil = 'Rohrleitung'")
            standard_options = [ft.dropdown.Option(row[0]) for row in cursor.fetchall()]
            
            # Festpreis manuell hinzufügen
            standard_options.append(ft.dropdown.Option("Festpreis"))

            # Bauteile mit Unit m2
            cursor.execute("SELECT DISTINCT Bauteil FROM price_list WHERE Unit = 'm2' AND Bauteil != 'Rohrleitung' ORDER BY Bauteil")
            m2_options = [ft.dropdown.Option(row[0]) for row in cursor.fetchall()]

            # Formteile aus der Faktoren-Tabelle
            cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Formteil' ORDER BY Bezeichnung")
            formteil_options = [ft.dropdown.Option(row[0]) for row in cursor.fetchall()]

            # Kleinkram (Unit = 'St')
            cursor.execute("SELECT DISTINCT Bauteil FROM price_list WHERE Unit = 'St' ORDER BY Bauteil")
            kleinkram_options = [ft.dropdown.Option(row[0]) for row in cursor.fetchall()]

            # Zusammensetzen der Optionen mit Gruppierungen
            self.position_fields['Bauteil'].options = [
                *standard_options,
                ft.dropdown.Option("--Bauteile (m²)--", disabled=True),
                *m2_options,
                ft.dropdown.Option("--Formteile--", disabled=True),
                *formteil_options,
                ft.dropdown.Option("--Kleinkram--", disabled=True),
                *kleinkram_options
            ]
        except Exception as e:
            logging.error(f"Fehler beim Laden der Bauteil-Optionen: {e}")
        finally:
            cursor.close()

    def load_options_for_position_field(self, field_name):
        cursor = self.conn.cursor()
        try:
            if field_name in ['DN', 'DA']:
                cursor.execute(f'SELECT DISTINCT {field_name} FROM price_list ORDER BY {field_name}')
                options = [row[0] for row in cursor.fetchall() if row[0] is not None]
                if field_name == 'DN':
                    options = [int(option) if option.is_integer() else option for option in options]
                self.position_fields[field_name].options = [ft.dropdown.Option(str(option)) for option in options]
            else:
                cursor.execute(f'SELECT DISTINCT {field_name} FROM price_list ORDER BY {field_name}')
                options = [row[0] for row in cursor.fetchall() if row[0] is not None]
                self.position_fields[field_name].options = [ft.dropdown.Option(str(option)) for option in options]
        except Exception as e:
            logging.error(f"Fehler beim Laden der Optionen für {field_name}: {e}")
        finally:
            cursor.close()

    def on_dropdown_change(self, e):
        field_name = next(key for key, value in self.invoice_detail_fields.items() if value == e.control)
        if e.control.value == "Neuer Eintrag":
            self.new_entry_fields[field_name].visible = True
        else:
            self.new_entry_fields[field_name].visible = False
        self.update()

    def get_invoice_data(self):
        invoice_data = {}
        for field_name, dropdown in self.invoice_detail_fields.items():
            if dropdown.value == "Neuer Eintrag":
                invoice_data[field_name] = self.new_entry_fields[field_name].value
            else:
                invoice_data[field_name] = dropdown.value
        return invoice_data

    def load_invoice_data(self, invoice_data):
        for field_name, value in invoice_data.items():
            if field_name in self.invoice_detail_fields:
                if value in [option.key for option in self.invoice_detail_fields[field_name].options]:
                    self.invoice_detail_fields[field_name].value = value
                else:
                    self.invoice_detail_fields[field_name].value = "Neuer Eintrag"
                    self.new_entry_fields[field_name].value = value
                    self.new_entry_fields[field_name].visible = True
        self.update()

    def show_sonderleistungen(self, e):
        # Implementierung für Sonderleistungen
        pass

    def add_position(self, e):
        # Implementierung zum Hinzufügen einer Position
        pass

    def on_bauteil_change(self, e):
        selected_bauteil = e.control.value
        cursor = self.conn.cursor()
        try:
            if selected_bauteil == "Festpreis":
                self.position_fields['Unit'].value = "pauschal"
            else:
                cursor.execute("SELECT Unit FROM price_list WHERE Bauteil = ? LIMIT 1", (selected_bauteil,))
                result = cursor.fetchone()
                if result:
                    self.position_fields['Unit'].value = result[0]
                else:
                    self.position_fields['Unit'].value = ""
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Mengeneinheit: {e}")
        finally:
            cursor.close()
        self.update()

    def on_dn_change(self, e):
        selected_dn = e.control.value
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT DA FROM price_list WHERE DN = ? LIMIT 1", (selected_dn,))
            result = cursor.fetchone()
            if result:
                self.position_fields['DA'].value = str(result[0])
            else:
                self.position_fields['DA'].value = None
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren des DA-Werts: {e}")
        finally:
            cursor.close()
        self.update()

    def on_da_change(self, e):
        selected_da = e.control.value
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT DN FROM price_list WHERE DA = ? LIMIT 1", (selected_da,))
            result = cursor.fetchone()
            if result:
                self.position_fields['DN'].value = str(int(result[0]) if result[0].is_integer() else result[0])
            else:
                self.position_fields['DN'].value = None
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren des DN-Werts: {e}")
        finally:
            cursor.close()
        self.update()