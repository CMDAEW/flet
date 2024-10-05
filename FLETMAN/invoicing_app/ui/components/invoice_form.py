import flet as ft
from database.db_operations import get_db_connection
import logging

class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.cache = {}
        self.previous_bauteil = None
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
            'Bauteil': ft.Dropdown(label="Bauteil", width=200, on_change=self.update_dn_da_fields),
            'DN': ft.Dropdown(label="DN", width=80, on_change=self.update_dn_fields),
            'DA': ft.Dropdown(label="DA", width=80, on_change=self.update_da_fields),
            'Size': ft.Dropdown(label="Dämmdicke", width=100, on_change=self.update_price),
            'Unit': ft.TextField(label="Einheit", width=100, read_only=True),
            'Taetigkeit': ft.Dropdown(label="Tätigkeit", width=300, on_change=self.update_price),
        }
        
        self.position_text_fields = {
            'Value': ft.TextField(label="Preis", width=100),
            'quantity': ft.TextField(label="Menge", width=100),
            'zwischensumme': ft.TextField(label="Zwischensumme", width=150, read_only=True),
        }

        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.show_sonderleistungen)
        self.add_position_button = ft.ElevatedButton("Hinzufügen", on_click=self.add_position)

    def update_price(self, e):
        # Hier können Sie die Logik zur Aktualisierung des Preises implementieren
        # Zum Beispiel:
        positionsnummer = self.position_fields['Positionsnummer'].value
        size = self.position_fields['Size'].value
        if positionsnummer and size:
            # Hier würden Sie den Preis aus der Datenbank abrufen
            # und das Value-Feld aktualisieren
            # Beispiel:
            # price = self.get_price_from_db(positionsnummer, size)
            # self.position_text_fields['Value'].value = str(price)
            # self.position_text_fields['Value'].update()
            pass

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

    def update_dn_da_fields(self, e):
        bauteil = self.position_fields['Bauteil'].value
        previous_bauteil = self.previous_bauteil
        is_rohrleitung_or_formteil = self.is_rohrleitung_or_formteil(bauteil)
        was_rohrleitung_or_formteil = self.is_rohrleitung_or_formteil(previous_bauteil)
        
        if bauteil:
            current_dn = self.position_fields['DN'].value
            current_da = self.position_fields['DA'].value
            current_dammdicke = self.position_fields['Size'].value

            if is_rohrleitung_or_formteil:
                all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
                
                self.position_fields['DN'].options = [ft.dropdown.Option(str(dn)) for dn in all_dn_options]
                self.position_fields['DA'].options = [ft.dropdown.Option(str(da)) for da in all_da_options]
                
                if current_dn in [opt.key for opt in self.position_fields['DN'].options]:
                    self.position_fields['DN'].value = current_dn
                else:
                    self.position_fields['DN'].value = str(all_dn_options[0]) if all_dn_options else None

                if current_da in [opt.key for opt in self.position_fields['DA'].options]:
                    self.position_fields['DA'].value = current_da
                else:
                    self.position_fields['DA'].value = str(all_da_options[0]) if all_da_options else None

                self.position_fields['DN'].visible = True
                self.position_fields['DA'].visible = True
            else:
                self.position_fields['DN'].value = None
                self.position_fields['DA'].value = None
                self.position_fields['DN'].visible = False
                self.position_fields['DA'].visible = False

            self.position_fields['DN'].update()
            self.position_fields['DA'].update()
            
            self.update_dammdicke_options()
            if current_dammdicke in [opt.key for opt in self.position_fields['Size'].options]:
                self.position_fields['Size'].value = current_dammdicke
            self.position_fields['Size'].update()

        if bauteil != previous_bauteil or is_rohrleitung_or_formteil != was_rohrleitung_or_formteil:
            self.update_price()
        
        self.previous_bauteil = bauteil
        self.update()

    def update_dn_fields(self, e):
        bauteil = self.position_fields['Bauteil'].value
        dn = self.position_fields['DN'].value
        if bauteil and self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.position_fields['DN'].options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            if dn:
                compatible_da = self.get_corresponding_da(bauteil, dn)
                new_da_value = str(compatible_da[0]) if compatible_da else None
                self.position_fields['DA'].value = new_da_value
                
                self.position_fields['DA'].options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
                self.position_fields['DA'].value = new_da_value
            else:
                self.position_fields['DA'].value = None
                self.position_fields['DA'].options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            self.position_fields['DA'].update()
        
        self.update_dammdicke_options()
        self.update_price()

    def update_da_fields(self, e):
        bauteil = self.position_fields['Bauteil'].value
        da = self.position_fields['DA'].value
        if bauteil and self.is_rohrleitung_or_formteil(bauteil):
            all_dn_options, all_da_options = self.load_all_dn_da_options(bauteil)
            
            self.position_fields['DA'].options = [ft.dropdown.Option(str(da_opt)) for da_opt in all_da_options]
            
            if da:
                compatible_dn = self.get_corresponding_dn(bauteil, da)
                new_dn_value = str(compatible_dn[0]) if compatible_dn else None
                self.position_fields['DN'].value = new_dn_value
                
                self.position_fields['DN'].options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
                self.position_fields['DN'].value = new_dn_value
            else:
                self.position_fields['DN'].value = None
                self.position_fields['DN'].options = [ft.dropdown.Option(str(dn_opt)) for dn_opt in all_dn_options]
            
            self.position_fields['DN'].update()
        
        self.update_dammdicke_options()
        self.update_price()
        self.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        if bauteil == 'Rohrleitung':
            return True
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
        return cursor.fetchone() is not None

    def get_from_cache_or_db(self, key, query, params=None):
        if key not in self.cache:
            cursor = self.conn.cursor()
            cursor.execute(query, params or ())
            self.cache[key] = cursor.fetchall()
        return self.cache[key]

    def load_all_dn_da_options(self, bauteil):
        all_dn_options = self.get_all_dn_options(bauteil)
        all_da_options = self.get_all_da_options(bauteil)
        return all_dn_options, all_da_options

    def get_all_dn_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DN IS NOT NULL ORDER BY DN'
            params = ('Rohrleitung',)
        else:
            return []

        options = self.get_from_cache_or_db(f"dn_options_{bauteil}", query, params)
        return [int(float(dn[0])) for dn in options]

    def get_all_da_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DA IS NOT NULL ORDER BY DA'
            params = ('Rohrleitung',)
        else:
            return []
    
        options = self.get_from_cache_or_db(f"da_options_{bauteil}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_da(self, bauteil, dn):
        query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DN = ? AND DA IS NOT NULL ORDER BY DA'
        params = (bauteil, dn)
        options = self.get_from_cache_or_db(f"da_options_{bauteil}_{dn}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_dn(self, bauteil, da):
        query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DA = ? AND DN IS NOT NULL ORDER BY DN'
        params = (bauteil, da)
        options = self.get_from_cache_or_db(f"dn_options_{bauteil}_{da}", query, params)
        return [int(float(dn[0])) for dn in options]