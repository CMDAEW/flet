import logging
import sqlite3
import flet as ft

def load_aufmass_items(self):
    cursor = self.conn.cursor()
    try:
        # Laden Sie Bauteile aus der Preisliste
        cursor.execute('''
            SELECT 
                CASE 
                    WHEN Size LIKE '%-%' THEN 'Kleinkram'
                    ELSE 'Bauteile'
                END AS Gruppe,
                Bauteil
            FROM 
                (SELECT DISTINCT Bauteil, Size FROM price_list)
            WHERE 
                Bauteil != 'Rohrleitung'
        ''')
        
        grouped_items = {'Bauteile': set(), 'Formteile': set(), 'Kleinkram': set()}
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
        
        options.append(ft.dropdown.Option("--- Kleinkram ---", disabled=True))
        options.extend([ft.dropdown.Option(bauteil) for bauteil in sorted(grouped_items['Kleinkram'])])

        self.bauteil_dropdown.options = options
        self.bauteil_dropdown.value = None
        
        # Laden Sie die Tätigkeiten
        cursor.execute('SELECT Bezeichnung FROM Faktoren WHERE Art = "Tätigkeit" ORDER BY Bezeichnung')
        taetigkeiten = [row[0] for row in cursor.fetchall()]
        self.taetigkeit_dropdown.options = [ft.dropdown.Option(taetigkeit) for taetigkeit in taetigkeiten]
        self.taetigkeit_dropdown.value = None
    finally:
        cursor.close()

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
    faktoren = self.get_from_cache_or_db(f"faktoren_{art}", 'SELECT Bezeichnung, Faktor FROM Faktoren WHERE Art = ?', (art,))
    if art == "Sonderleistung":
        container = self.sonderleistungen_container.content
    else:
        container = self.zuschlaege_container
    container.controls.clear()
    for bezeichnung, faktor in faktoren:
        checkbox = ft.Checkbox(label=f"{bezeichnung}", value=False)
        checkbox.on_change = lambda e, b=bezeichnung, f=faktor: self.update_selected_faktoren(e, b, f, art)
        container.controls.append(checkbox)
    self.update()

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
    cursor = self.conn.cursor()
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

def get_base_price(self, bauteil, dn, da, dammdicke):
    cursor = self.conn.cursor()
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

def get_material_price(self, bauteil):
    cursor = self.conn.cursor()
    try:
        cursor.execute("SELECT Preis FROM Materialpreise WHERE Benennung = ?", (bauteil,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()

def get_taetigkeit_faktor(self, taetigkeit):
    cursor = self.conn.cursor()
    try:
        cursor.execute('SELECT Faktor FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()

def get_positionsnummer(self, bauteil, dammdicke, dn=None, da=None, category="Aufmaß"):
    cursor = self.conn.cursor()
    try:
        if category == "Aufmaß":
            # Hole zuerst die Tätigkeits-ID
            taetigkeit = self.taetigkeit_dropdown.value
            cursor.execute('SELECT id FROM Faktoren WHERE Art = "Tätigkeit" AND Bezeichnung = ?', (taetigkeit,))
            taetigkeit_id = cursor.fetchone()
            if not taetigkeit_id:
                logging.warning(f"Keine Tätigkeits-ID gefunden für: {taetigkeit}")
                return None
            taetigkeit_id = taetigkeit_id[0]

            if self.is_formteil(bauteil):
                # Logik für Formteile
                cursor.execute('SELECT id FROM Faktoren WHERE Art = "Formteil" AND Bezeichnung = ?', (bauteil,))
                formteil_id = cursor.fetchone()
                if not formteil_id:
                    logging.warning(f"Keine Formteil-ID gefunden für: {bauteil}")
                    return None
                formteil_id = formteil_id[0]

                cursor.execute("SELECT Positionsnummer FROM price_list WHERE Bauteil = 'Rohrleitung' AND Size = ? AND DN = ? AND DA = ? LIMIT 1", (dammdicke, dn, da))
                rohrleitung_nummer = cursor.fetchone()
                if not rohrleitung_nummer:
                    logging.warning(f"Keine Rohrleitung-Nummer gefunden für: Dämmdicke={dammdicke}, DN={dn}, DA={da}")
                    return None
                rohrleitung_nummer = rohrleitung_nummer[0]

                return f"{taetigkeit_id}.{formteil_id}.{rohrleitung_nummer}"

            elif self.is_rohrleitung(bauteil):
                # Logik für Rohrleitungen
                query = "SELECT Positionsnummer FROM price_list WHERE Bauteil = 'Rohrleitung' AND Size = ? AND DN = ? AND DA = ? LIMIT 1"
                cursor.execute(query, (dammdicke, dn, da))
                bauteil_nummer = cursor.fetchone()
                
                if bauteil_nummer:
                    return f"{taetigkeit_id}.{bauteil_nummer[0]}"
                else:
                    logging.warning(f"Keine Rohrleitung-Nummer gefunden für: Dämmdicke={dammdicke}, DN={dn}, DA={da}")
                    return None

            else:
                # Logik für andere Bauteile
                query = "SELECT Positionsnummer FROM price_list WHERE Bauteil = ? AND Size = ? LIMIT 1"
                cursor.execute(query, (bauteil, dammdicke))
                bauteil_nummer = cursor.fetchone()
                
                if bauteil_nummer:
                    return f"{taetigkeit_id}.{bauteil_nummer[0]}"
                else:
                    logging.warning(f"Keine Bauteil-Nummer gefunden für: Bauteil={bauteil}, Dämmdicke={dammdicke}")
                    return None

        elif category == "Material":
            cursor.execute("SELECT Positionsnummer FROM Materialpreise WHERE Benennung = ? LIMIT 1", (bauteil,))
            result = cursor.fetchone()
            return result[0] if result else None
        else:
            logging.warning(f"Unbekannte Kategorie: {category}")
            return None
    finally:
        cursor.close()

def update_price(self, e=None):
    category = self.current_category
    bauteil = self.bauteil_dropdown.value
    dn = self.dn_dropdown.value if self.dn_dropdown.visible else None
    da = self.da_dropdown.value if self.da_dropdown.visible else None
    dammdicke = self.dammdicke_dropdown.value
    taetigkeit = self.taetigkeit_dropdown.value
    quantity = self.quantity_input.value

    if not all([category, bauteil, quantity]):
        self.price_field.value = ""
        self.zwischensumme_field.value = ""
        return

    try:
        quantity = float(quantity)
    except ValueError:
        self.show_error("Ungültige Menge")
        self.price_field.value = ""
        self.zwischensumme_field.value = ""
        return

    # Hole die Positionsnummer
    positionsnummer = get_positionsnummer(self, bauteil, dammdicke, dn, da, category)
    if positionsnummer:
        self.position_field.value = str(positionsnummer)
    else:
        self.position_field.value = ""

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
    cursor = self.conn.cursor()
    try:
        cursor.execute('SELECT DISTINCT Bauteil FROM price_list WHERE Category = "Material" ORDER BY Bauteil')
        items = [row[0] for row in cursor.fetchall()]
        self.bauteil_dropdown.options = [ft.dropdown.Option(item) for item in items]
        self.bauteil_dropdown.value = None
    finally:
        cursor.close()

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