import flet as ft
from database.db_operations import get_db_connection
import logging

# Am Anfang der Datei, nach den Importen
ROHRLEITUNG = "Rohrleitung"
FORMTEIL = "Formteil"

class InvoiceForm(ft.UserControl):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.conn = get_db_connection()
        self.cache = {}
        self.previous_bauteil = None
        self.create_ui_elements()
        self.load_data()
        # Entfernen Sie den Aufruf von self.initialize_taetigkeit() hier

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
            'Positionsnummer': ft.Dropdown(
                label="Positionsnummer",
                width=200,
                on_change=self.update_from_positionsnummer,
            ),
            'DN': ft.Dropdown(label="DN", width=80),
            'DA': ft.Dropdown(label="DA", width=80),
            'Size': ft.Dropdown(label="Dämmdicke", width=100),
            'Bauteil': ft.Dropdown(label="Bauteil", width=200),
            'Unit': ft.TextField(label="Einheit", width=80, read_only=True),
            'Taetigkeit': ft.Dropdown(label="Tätigkeit", width=200),
        }
        
        self.position_text_fields = {
            'Value': ft.TextField(label="Preis", width=100),
            'quantity': ft.TextField(label="Menge", width=100, value="1", on_change=self.update_zwischensumme),
            'zwischensumme': ft.TextField(label="Zwischensumme", width=150, read_only=True),
        }

        self.sonderleistungen_button = ft.ElevatedButton("Sonderleistungen", on_click=self.show_sonderleistungen)
        self.add_position_button = ft.ElevatedButton("Hinzufügen", on_click=self.add_position)

        # Entfernen Sie den Aufruf von self.initialize_taetigkeit() hier

    def did_mount(self):
        # Diese Methode wird aufgerufen, nachdem das Control der Seite hinzugefügt wurde
        self.initialize_taetigkeit()
        self.update()

    def initialize_taetigkeit(self):
        if 'Taetigkeit' in self.position_fields:
            self.position_fields['Taetigkeit'].value = "keine Deremontage"
            # Entfernen Sie den Aufruf von update() hier, da es nicht nötig ist

    def update_price(self, e=None):
        bauteil = self.position_fields['Bauteil'].value
        dn = self.position_fields['DN'].value if self.position_fields['DN'].visible else None
        da = self.position_fields['DA'].value if self.position_fields['DA'].visible else None
        size = self.position_fields['Size'].value
        taetigkeit = self.position_fields['Taetigkeit'].value

        if not all([bauteil, size, taetigkeit]):
            self.position_text_fields['Value'].value = "Unvollständige Daten"
            self.update_zwischensumme()
            return

        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                cursor.execute("""
                    SELECT Value FROM price_list 
                    WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?
                """, (ROHRLEITUNG, dn, da, size))
            else:
                cursor.execute("""
                    SELECT Value FROM price_list 
                    WHERE Bauteil = ? AND Size = ?
                """, (bauteil, size))
            
            result = cursor.fetchone()
            if result:
                base_price = result[0]
                
                cursor.execute("""
                    SELECT Faktor FROM Faktoren 
                    WHERE Art = 'Tätigkeit' AND Bezeichnung = ?
                """, (taetigkeit,))
                taetigkeit_result = cursor.fetchone()
                if taetigkeit_result:
                    taetigkeit_faktor = taetigkeit_result[0]
                    final_price = base_price * taetigkeit_faktor
                    self.position_text_fields['Value'].value = f"{final_price:.2f}"
                else:
                    self.position_text_fields['Value'].value = "Tätigkeitsfaktor nicht gefunden"
            else:
                self.position_text_fields['Value'].value = "Preis nicht gefunden"
        except Exception as e:
            logging.error(f"Fehler bei der Preisberechnung: {e}")
            self.position_text_fields['Value'].value = "Fehler bei der Berechnung"
        finally:
            cursor.close()
        
        self.update_zwischensumme()
        self.update()

    def update_zwischensumme(self, e=None):
        try:
            preis = float(self.position_text_fields['Value'].value or 0)
            menge = float(self.position_text_fields['quantity'].value or 1)
            zwischensumme = preis * menge
            self.position_text_fields['zwischensumme'].value = f"{zwischensumme:.2f}"
        except ValueError:
            self.position_text_fields['zwischensumme'].value = "Ungültige Eingabe"
        self.update()

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
            self.position_fields['Positionsnummer'],
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
        self.load_positionsnummer_options()

    def load_invoice_options(self):
        for field_name in self.invoice_detail_fields:
            self.load_options_for_field(field_name)

    def load_position_options(self):
        self.load_bauteil_options()
        self.load_taetigkeit_options()
        for field_name, dropdown in self.position_fields.items():
            if field_name not in ['Bauteil', 'Taetigkeit']:
                self.load_options_for_position_field(field_name)

    def load_positionsnummer_options(self):
        cursor = self.conn.cursor()
        try:
            # Lade Positionsnummern aus der price_list Tabelle
            cursor.execute("SELECT DISTINCT Positionsnummer FROM price_list ORDER BY Positionsnummer")
            price_list_options = [row[0] for row in cursor.fetchall() if row[0]]

            # Lade Positionsnummern aus der Faktoren Tabelle für Formteile
            cursor.execute("SELECT DISTINCT Positionsnummer FROM Faktoren WHERE Art = 'Formteil' ORDER BY Positionsnummer")
            formteil_options = [row[0] for row in cursor.fetchall() if row[0]]

            # Kombiniere und entferne Duplikate
            all_options = list(set(price_list_options + formteil_options))
            all_options.sort()

            self.position_fields['Positionsnummer'].options = [ft.dropdown.Option(option) for option in all_options]
        except Exception as e:
            logging.error(f"Fehler beim Laden der Positionsnummer-Optionen: {e}")
        finally:
            cursor.close()

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
            self.update_unit(bauteil)
            self.update_positionsnummer()
            current_dn = self.position_fields['DN'].value
            current_da = self.position_fields['DA'].value

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

        if bauteil != previous_bauteil or is_rohrleitung_or_formteil != was_rohrleitung_or_formteil:
            self.update_price()
        
        self.previous_bauteil = bauteil
        self.update()

    def update_unit(self, bauteil):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT Unit FROM price_list WHERE Bauteil = ? LIMIT 1", (bauteil,))
            result = cursor.fetchone()
            if result:
                self.position_fields['Unit'].value = result[0]
            else:
                self.position_fields['Unit'].value = ""
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Einheit: {e}")
        finally:
            cursor.close()
        self.position_fields['Unit'].update()

    def update_dammdicke_options(self, e=None):
        bauteil = self.position_fields['Bauteil'].value
        if not bauteil:
            return

        dn = self.position_fields['DN'].value if self.position_fields['DN'].visible else None
        da = self.position_fields['DA'].value if self.position_fields['DA'].visible else None

        dammdicke_options = self.get_dammdicke_options(bauteil, dn, da)
        self.position_fields['Size'].options = [ft.dropdown.Option(str(size)) for size in dammdicke_options]
        if dammdicke_options:
            self.position_fields['Size'].value = str(dammdicke_options[0])
        else:
            self.position_fields['Size'].value = None
        self.position_fields['Size'].update()
        
        # Aktualisiere die Positionsnummer, wenn sich die Dämmdicke ändert
        self.update_positionsnummer()
        
        # Aktualisiere den Preis
        self.update_price()

    def get_dammdicke_options(self, bauteil, dn=None, da=None):
        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                if dn and da:
                    cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size IS NOT NULL ORDER BY Size', ('Rohrleitung', dn, da))
                else:
                    cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND Size IS NOT NULL ORDER BY Size', ('Rohrleitung',))
            else:
                cursor.execute('SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? AND Size IS NOT NULL ORDER BY Size', (bauteil,))
            
            sizes = [row[0] for row in cursor.fetchall()]
            return sorted(set(sizes), key=lambda x: float(x.split()[0]) if isinstance(x, str) and x.split()[0].replace('.', '').isdigit() else x)
        finally:
            cursor.close()

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
        self.update_positionsnummer()
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
        self.update_positionsnummer()
        self.update_price()
        self.update()

    def is_rohrleitung_or_formteil(self, bauteil):
        if bauteil == ROHRLEITUNG:
            return True
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM Faktoren WHERE Art = ? AND Bezeichnung = ?', (FORMTEIL, bauteil))
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
            params = (ROHRLEITUNG,)
        else:
            return []

        options = self.get_from_cache_or_db(f"dn_options_{bauteil}", query, params)
        return [int(float(dn[0])) for dn in options]

    def get_all_da_options(self, bauteil):
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DA IS NOT NULL ORDER BY DA'
            params = (ROHRLEITUNG,)
        else:
            return []
    
        options = self.get_from_cache_or_db(f"da_options_{bauteil}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_da(self, bauteil, dn):
        query = 'SELECT DISTINCT DA FROM price_list WHERE Bauteil = ? AND DN = ? AND DA IS NOT NULL ORDER BY DA'
        params = (ROHRLEITUNG, dn)
        options = self.get_from_cache_or_db(f"da_options_{ROHRLEITUNG}_{dn}", query, params)
        return [float(da[0]) for da in options]

    def get_corresponding_dn(self, bauteil, da):
        query = 'SELECT DISTINCT DN FROM price_list WHERE Bauteil = ? AND DA = ? AND DN IS NOT NULL ORDER BY DN'
        params = (ROHRLEITUNG, da)
        options = self.get_from_cache_or_db(f"dn_options_{ROHRLEITUNG}_{da}", query, params)
        return [int(float(dn[0])) for dn in options]

    def update_from_positionsnummer(self, e):
        positionsnummer = self.position_fields['Positionsnummer'].value
        if positionsnummer:
            cursor = self.conn.cursor()
            try:
                # Zuerst in der price_list Tabelle suchen
                cursor.execute("""
                    SELECT Bauteil, DN, DA, Size, Unit, Value
                    FROM price_list
                    WHERE Positionsnummer = ?
                """, (positionsnummer,))
                result = cursor.fetchone()
                
                if not result:
                    # Wenn nicht gefunden, in der Faktoren Tabelle für Formteile suchen
                    cursor.execute("""
                        SELECT Bezeichnung
                        FROM Faktoren
                        WHERE Art = 'Formteil' AND Positionsnummer = ?
                    """, (positionsnummer,))
                    formteil_result = cursor.fetchone()
                    if formteil_result:
                        bauteil = formteil_result[0]
                        # Für Formteile setzen wir DN, DA, und Size auf None, da sie später basierend auf der Rohrleitung ausgewählt werden
                        result = (bauteil, None, None, None, 'm2', None)

                if result:
                    bauteil, dn, da, size, unit, value = result
                    self.position_fields['Bauteil'].value = bauteil
                    self.position_fields['DN'].value = str(dn) if dn else None
                    self.position_fields['DA'].value = str(da) if da else None
                    self.position_fields['Size'].value = str(size) if size else None
                    self.position_fields['Unit'].value = unit
                    self.position_text_fields['Value'].value = str(value) if value else None
                    
                    # Setze das Tätigkeitsfeld auf "keine Deremontage"
                    self.position_fields['Taetigkeit'].value = "keine Deremontage"
                    
                    self.update_dn_da_fields(None)
                    self.update_price()
                    self.update_zwischensumme()
                else:
                    logging.warning(f"Keine Daten für Positionsnummer {positionsnummer} gefunden.")
            except Exception as e:
                logging.error(f"Fehler beim Aktualisieren der Felder von der Positionsnummer: {e}")
            finally:
                cursor.close()
        self.update()

    def update_positionsnummer(self):
        bauteil = self.position_fields['Bauteil'].value
        dn = self.position_fields['DN'].value
        da = self.position_fields['DA'].value
        size = self.position_fields['Size'].value

        cursor = self.conn.cursor()
        try:
            if self.is_rohrleitung_or_formteil(bauteil):
                cursor.execute("""
                    SELECT Positionsnummer
                    FROM price_list
                    WHERE Bauteil = ? AND DN = ? AND DA = ? AND Size = ?
                """, (bauteil, dn, da, size))
            else:
                cursor.execute("""
                    SELECT Positionsnummer
                    FROM price_list
                    WHERE Bauteil = ? AND Size = ?
                """, (bauteil, size))
            result = cursor.fetchone()
            if result:
                self.position_fields['Positionsnummer'].value = result[0]
            else:
                self.position_fields['Positionsnummer'].value = ""
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Positionsnummer: {e}")
        finally:
            cursor.close()
        self.position_fields['Positionsnummer'].update()