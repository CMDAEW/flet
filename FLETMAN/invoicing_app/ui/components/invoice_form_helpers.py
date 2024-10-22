import logging
import sqlite3
import flet as ft
from database.db_operations import get_db_connection

def load_aufmass_items(self):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Laden Sie Bauteile aus der Preisliste
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN Size LIKE '%-%' THEN 'Kleinteile'
                    ELSE 'Bauteile'
                END AS Gruppe,
                Bauteil
            FROM 
                (SELECT DISTINCT Bauteil, Size FROM price_list)
            WHERE 
                Bauteil != 'Rohrleitung'
        ''')
        
        grouped_items = {'Bauteile': set(), 'Formteile': set(), 'Kleinteile': set()}
        for gruppe, bauteil in cursor.fetchall():
            grouped_items[gruppe].add(bauteil)

        # Laden Sie Formteile aus der Faktoren-Tabelle
        cursor.execute('''
            SELECT Bezeichnung
            FROM Faktoren
            WHERE Art = 'Formteil'
        ''')
        formteile = cursor.fetchall()
        grouped_items['Formteile'] = set(item[0] for item in formteile)

        # Erstellen Sie die Optionen für das Dropdown
        options = [
            ft.dropdown.Option("Rohrleitung"),  # Rohrleitung als erste Option
            ft.dropdown.Option("--- Bauteile ---", disabled=True)
        ]
        options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Bauteile'])])
        
        options.append(ft.dropdown.Option("--- Formteile ---", disabled=True))
        options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Formteile'])])
        
        options.append(ft.dropdown.Option("--- Kleinteile ---", disabled=True))
        options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Kleinteile'])])

        self.bauteil_dropdown.options = options
        self.bauteil_dropdown.value = None
        
        # Laden Sie die Tätigkeiten
        cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung')
        taetigkeiten = [row[0] for row in cursor.fetchall()]
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.value = None
    finally:
        cursor.close()
        conn.close()

    self.update()

def load_items(self, category):
    if category == "Aufmaß":
        load_aufmass_items(self)
    elif category == "Material":
        load_material_items(self)
    elif category == "Lohn":
        load_lohn_items(self)
    elif category == "Festpreis":
        load_festpreis_items(self)
    self.update_field_visibility()

def load_faktoren(self, art):
    cursor = self.conn.cursor()
    try:
        cursor.execute('SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
        faktoren = cursor.fetchall()
        
        if art == "Sonderleistung":
            # Speichern Sie die Sonderleistungen in der options Liste
            self.sonderleistungen_options = [
                (bezeichnung, float(faktor)) for bezeichnung, faktor in faktoren
            ]
        elif art == "Zuschlag":
            # Bestehende Logik für Zuschläge beibehalten
            if hasattr(self, 'zuschlaege_container') and self.zuschlaege_container:
                container = self.zuschlaege_container.content
                container.controls.clear()
                for bezeichnung, faktor in faktoren:
                    checkbox = ft.Checkbox(
                        label=f"{bezeichnung} ({faktor})",
                        on_change=lambda e, b=bezeichnung, f=faktor: self.update_selected_zuschlaege(e, b, f)
                    )
                    container.controls.append(checkbox)
    finally:
        cursor.close()

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

def get_dammdicke_options(self, bauteil, dn=None, da=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if self.is_rohrleitung_or_formteil(bauteil):
            query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? ORDER BY CAST(Size AS FLOAT)'
            params = (dn, da)
        else:
            query = 'SELECT DISTINCT Size FROM price_list WHERE Bauteil = ? ORDER BY CAST(Size AS FLOAT)'
            params = (bauteil,)
        
        cursor.execute(query, params)
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def get_base_price(self, bauteil, dn, da, dammdicke):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if self.is_rohrleitung_or_formteil(bauteil):
            if self.is_formteil(bauteil):
                cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
                formteil_faktor = cursor.fetchone()
                if formteil_faktor:
                    cursor.execute('SELECT Value FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? AND Size = ?', (dn, da, dammdicke))
                    base_price = cursor.fetchone()
                    if base_price:
                        return base_price[0] * formteil_faktor[0]
            else:
                cursor.execute('SELECT Value FROM price_list WHERE Bauteil = "Rohrleitung" AND DN = ? AND DA = ? AND Size = ?', (dn, da, dammdicke))
                result = cursor.fetchone()
                if result:
                    return result[0]
        else:
            cursor.execute('SELECT Value FROM price_list WHERE Bauteil = ? AND Size = ?', (bauteil, dammdicke))
            result = cursor.fetchone()
            if result:
                return result[0]
        return None
    finally:
        cursor.close()
        conn.close()

def get_material_price(self, bauteil):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Zuerst überprüfen wir die Struktur der Tabelle
        cursor.execute("PRAGMA table_info(Materialpreise)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Wir suchen nach einer Spalte, die "preis" oder "price" enthält (Groß-/Kleinschreibung ignorieren)
        price_column = next((col for col in columns if "preis" in col.lower() or "price" in col.lower()), None)
        
        if price_column:
            cursor.execute(f"SELECT {price_column} FROM Materialpreise WHERE Benennung = ?", (bauteil,))
            result = cursor.fetchone()
            return result[0] if result else None
        else:
            logging.error("Keine Preis-Spalte in der Materialpreise-Tabelle gefunden")
            return None
    except sqlite3.Error as e:
        logging.error(f"Datenbankfehler in get_material_price: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_taetigkeit_faktor(self, taetigkeit):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        conn.close()

def get_positionsnummer(self, bauteil, dammdicke, dn, da, category):
    if category == "Material":
        return "M"
    elif self.is_rohrleitung(bauteil):
        if dn and da:
            return f"{dn}.{da}.{dammdicke}"
        else:
            return f"50.{dammdicke}"
    elif self.is_formteil(bauteil):
        if dn and da:
            return f"51.{dn}.{da}.{dammdicke}"
        else:
            return f"51.{dammdicke}"
    else:
        bauteil_code = {
            "Armatur": "52",
            "Flansch": "53",
            "Tankmantel/Glattblech": "54",
            "Tankboden": "55",
            "Tankdach": "56",
            "Stutzen": "57",
            "Behälter": "58",
            "Apparat": "59",
            "Kanal": "60"
        }.get(bauteil, "50")
        return f"{bauteil_code}.{dammdicke}"

def update_price(self, e=None):
    bauteil = self.bauteil_dropdown.value
    dammdicke = self.dammdicke_dropdown.value
    dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
    da = self.da_dropdown.value if self.da_dropdown.visible else None
    taetigkeit = self.taetigkeit_dropdown.value
    category = self.current_category
    quantity = self.quantity_input.value

    # Überprüfen Sie, ob alle notwendigen Felder ausgefüllt sind
    if not all([category, bauteil]):
        self.price_field.value = ""
        self.zwischensumme_field.value = ""
        return

    try:
        quantity = float(quantity) if quantity else 0
    except ValueError:
        self.show_error("Ungültige Menge")
        self.price_field.value = ""
        self.zwischensumme_field.value = ""
        return

    if bauteil is not None:
        positionsnummer = get_positionsnummer(self, bauteil, dammdicke, dn, da, category)
    else:
        positionsnummer = None

    if positionsnummer:
        self.position_field.value = str(positionsnummer)
    else:
        self.position_field.value = ""

    price = 0

    if category == "Aufmaß":
        if not all([taetigkeit, dammdicke]):
            return

        base_price = get_base_price(self, bauteil, dn, da, dammdicke)
        if base_price is None:
            self.show_error("Kein Preis gefunden")
            return

        taetigkeit_faktor = get_taetigkeit_faktor(self, taetigkeit)
        if taetigkeit_faktor is None:
            self.show_error("Kein Tätigkeitsfaktor gefunden")
            return

        price = base_price * taetigkeit_faktor

        # Anwenden von Sonderleistungen
        for _, faktor in self.selected_sonderleistungen:
            price *= faktor

    elif category == "Material":
        price = get_material_price(self, bauteil)
        if price is None:
            self.show_error("Kein Materialpreis gefunden")
            return

    else:
        # Für andere Kategorien (z.B. Lohn, Festpreis) müssen Sie hier die entsprechende Logik implementieren
        self.show_error("Preisberechnung für diese Kategorie nicht implementiert")
        return

    total_price = price * quantity

    self.price_field.value = f"{price:.2f}"
    self.zwischensumme_field.value = f"{total_price:.2f}"
    
    self.update()

def load_material_items(self):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT DISTINCT Bauteil FROM price_list WHERE Category = "Material" ORDER BY Bauteil')
        items = [row[0] for row in cursor.fetchall()]
        self.bauteil_dropdown.options = [ft.dropdown.Option(item) for item in items]
        self.bauteil_dropdown.value = None
    finally:
        cursor.close()
        conn.close()

def load_lohn_items(self):
    # Implementieren Sie hier die Logik zum Laden der Lohn-Artikel
    pass

def load_festpreis_items(self):
    # Implementieren Sie hier die Logik zum Laden der Festpreis-Artikel
    pass

# Neue Funktion zur Anwendung der Zuschläge auf den Gesamtbetrag
# Neue Funktion zur Anwendung der Zuschläge auf den Gesamtbetrag
def apply_zuschlaege(self, total_amount):
    for _, faktor in self.selected_zuschlaege:
        total_amount *= faktor
    return total_amount











