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
            'DN': ft.Dropdown(label="DN", width=80, on_change=self.on_dn_change, visible=True),
            'DA': ft.Dropdown(label="DA", width=80, on_change=self.on_da_change, visible=True),
            'Size': ft.Dropdown(label="Dämmdicke", width=100),
            'Unit': ft.TextField(label="Einheit", width=100, read_only=True),  # Geändert von "Mengeneinheit" zu "Einheit"
            'Taetigkeit': ft.Dropdown(label="Tätigkeit", width=300),
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
            self.position_fields['Taetigkeit'],
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
        self.load_taetigkeit_options()
        for field_name, dropdown in self.position_fields.items():
            if field_name not in ['Bauteil', 'Taetigkeit']:
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

    def load_taetigkeit_options(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT Bezeichnung FROM Faktoren WHERE Art = 'Tätigkeit' ORDER BY Bezeichnung")
            options = [row[0] for row in cursor.fetchall()]
            self.position_fields['Taetigkeit'].options = [ft.dropdown.Option(option) for option in options]
        except Exception as e:
            logging.error(f"Fehler beim Laden der Tätigkeits-Optionen: {e}")
        finally:
            cursor.close()

    def load_options_for_position_field(self, field_name):
        cursor = self.conn.cursor()
        try:
            if field_name in ['DN', 'DA']:
                cursor.execute(f'SELECT DISTINCT {field_name} FROM price_list WHERE {field_name} IS NOT NULL ORDER BY {field_name}')
                options = [row[0] for row in cursor.fetchall()]
                if field_name == 'DN':
                    options = [int(option) if isinstance(option, float) and option.is_integer() else option for option in options]
                self.position_fields[field_name].options = [ft.dropdown.Option(str(option)) for option in options]
            elif field_name != 'Size':  # Size wird separat behandelt
                cursor.execute(f'SELECT DISTINCT {field_name} FROM price_list WHERE {field_name} IS NOT NULL ORDER BY {field_name}')
                options = [row[0] for row in cursor.fetchall()]
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
                self.position_fields['DN'].visible = False
                self.position_fields['DA'].visible = False
                self.position_fields['Size'].options = []
            else:
                cursor.execute("SELECT Unit FROM price_list WHERE Bauteil = ? LIMIT 1", (selected_bauteil,))
                result = cursor.fetchone()
                if result:
                    unit = result[0]
                    self.position_fields['Unit'].value = unit
                    if unit in ['St', 'm2']:
                        self.position_fields['DN'].visible = False
                        self.position_fields['DA'].visible = False
                        # Laden der verfügbaren Dämmdicken für dieses Bauteil
                        self.load_size_options(selected_bauteil)
                    else:
                        self.position_fields['DN'].visible = True
                        self.position_fields['DA'].visible = True
                        # Laden der DN und DA Optionen für das ausgewählte Bauteil
                        self.load_dn_da_options(selected_bauteil)
                        # Automatisch die ersten verfügbaren Werte für DN und DA auswählen
                        if self.position_fields['DN'].options:
                            self.position_fields['DN'].value = self.position_fields['DN'].options[0].key
                        if self.position_fields['DA'].options:
                            self.position_fields['DA'].value = self.position_fields['DA'].options[0].key
                        # Dämmdicken basierend auf den ausgewählten DN und DA Werten laden
                        self.update_size_options()
                else:
                    self.position_fields['Unit'].value = ""
                    self.position_fields['DN'].visible = True
                    self.position_fields['DA'].visible = True
                    self.position_fields['Size'].options = []
            
            # Zurücksetzen der Werte für Size
            self.position_fields['Size'].value = None
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Felder nach Bauteil-Änderung: {e}")
        finally:
            cursor.close()
        self.update()

    def load_size_options(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT Size 
                FROM price_list 
                WHERE Bauteil = ? AND Size IS NOT NULL
                ORDER BY CAST(Size AS INTEGER)
            """, (bauteil,))
            size_options = [row[0] for row in cursor.fetchall()]
            self.position_fields['Size'].options = [ft.dropdown.Option(str(option)) for option in size_options]
            
            # Automatisch die erste Größenoption auswählen, wenn verfügbar
            if size_options:
                self.position_fields['Size'].value = str(size_options[0])
            else:
                self.position_fields['Size'].value = None
        except Exception as e:
            logging.error(f"Fehler beim Laden der Dämmdicken-Optionen für Bauteil {bauteil}: {e}")
        finally:
            cursor.close()

    def load_dn_da_options(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT DN, DA FROM price_list WHERE Bauteil = ? AND DN IS NOT NULL AND DA IS NOT NULL ORDER BY DN, DA", (bauteil,))
            dn_da_pairs = cursor.fetchall()
            
            dn_options = sorted(set(pair[0] for pair in dn_da_pairs))
            da_options = sorted(set(pair[1] for pair in dn_da_pairs))
            
            self.position_fields['DN'].options = [ft.dropdown.Option(str(int(dn) if isinstance(dn, float) and dn.is_integer() else dn)) for dn in dn_options]
            self.position_fields['DA'].options = [ft.dropdown.Option(str(da)) for da in da_options]
            
            # Speichern der DN-DA Paare für spätere Verwendung
            self.dn_da_pairs = dn_da_pairs
        except Exception as e:
            logging.error(f"Fehler beim Laden der DN/DA Optionen für Bauteil {bauteil}: {e}")
        finally:
            cursor.close()

    def on_dn_change(self, e):
        selected_dn = e.control.value
        if selected_dn:
            matching_das = [pair[1] for pair in self.dn_da_pairs if str(pair[0]) == selected_dn]
            if matching_das:
                # Wähle den ersten korrespondierenden DA-Wert aus
                da_value = str(matching_das[0])
                self.position_fields['DA'].value = da_value
                self.position_fields['DA'].visible = True
                # Aktualisiere die Dämmdicken-Optionen
                self.update_size_options()
            else:
                # Wenn kein passendes DA gefunden wird, setzen wir es auf None, aber lassen es sichtbar
                self.position_fields['DA'].value = None
                self.position_fields['DA'].visible = True
                self.position_fields['Size'].options = []
                self.position_fields['Size'].value = None
        else:
            self.position_fields['DA'].value = None
            self.position_fields['DA'].visible = True
            self.position_fields['Size'].options = []
            self.position_fields['Size'].value = None
        
        # Erzwinge ein Update des DA-Feldes
        self.position_fields['DA'].update()
        self.update()

    def on_da_change(self, e):
        selected_da = e.control.value
        if selected_da:
            matching_dns = [pair[0] for pair in self.dn_da_pairs if str(pair[1]) == selected_da]
            if matching_dns:
                self.position_fields['DN'].value = str(int(matching_dns[0]) if isinstance(matching_dns[0], float) and matching_dns[0].is_integer() else matching_dns[0])
            else:
                # Wenn kein passendes DN gefunden wird, setzen wir es auf None, aber lassen es sichtbar
                self.position_fields['DN'].value = None
            self.update_size_options()
        else:
            self.position_fields['DN'].value = None
            self.position_fields['Size'].options = []
            self.position_fields['Size'].value = None
        self.update()

    def update_size_options(self):
        selected_bauteil = self.position_fields['Bauteil'].value
        selected_dn = self.position_fields['DN'].value
        selected_da = self.position_fields['DA'].value
        
        if selected_bauteil and selected_dn and selected_da:
            cursor = self.conn.cursor()
            try:
                cursor.execute("""
                    SELECT DISTINCT Size 
                    FROM price_list 
                    WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size IS NOT NULL
                    ORDER BY CAST(Size AS INTEGER)
                """, (selected_bauteil, selected_dn, selected_da))
                size_options = [row[0] for row in cursor.fetchall()]
                self.position_fields['Size'].options = [ft.dropdown.Option(str(option)) for option in size_options]
                
                # Automatisch die erste Größenoption auswählen, wenn verfügbar
                if size_options:
                    self.position_fields['Size'].value = str(size_options[0])
                else:
                    self.position_fields['Size'].value = None
                
                # Size-Feld immer sichtbar lassen
                self.position_fields['Size'].visible = True
            except Exception as e:
                logging.error(f"Fehler beim Aktualisieren der Dämmdicken-Optionen: {e}")
            finally:
                cursor.close()
        else:
            self.position_fields['Size'].options = []
            self.position_fields['Size'].value = None
            # Size-Feld immer sichtbar lassen
            self.position_fields['Size'].visible = True
        
        # Erzwinge ein Update des Size-Feldes
        self.position_fields['Size'].update()
        self.update()