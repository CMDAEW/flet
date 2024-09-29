# -*- coding: utf-8 -*-
import logging
import flet as ft
import sqlite3
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from database_setup import get_db_connection, initialize_database, get_unique_bauteil_values, get_unique_dn_da_pairs

def rechnung_einfuegen(client_name, client_email, invoice_date, total, items):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert into invoices table
        cursor.execute('''
            INSERT INTO invoices (client_name, client_email, invoice_date, total)
            VALUES (?, ?, ?, ?)
        ''', (client_name, client_email, invoice_date, total))
        invoice_id = cursor.lastrowid
        
        # Insert items into invoice_items table
        for item in items:
            cursor.execute('''
                INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (invoice_id, item['description'], item.get('dn'), item.get('da'), item.get('size'), item['price'], item['quantity']))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

def rechnung_aktualisieren(id, client_name, client_email, invoice_date, total, items):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE invoices 
        SET client_name=?, client_email=?, invoice_date=?, total=?
        WHERE id=?
    ''', (client_name, client_email, invoice_date, total, id))
    
    cursor.execute('DELETE FROM invoice_items WHERE invoice_id=?', (id,))
    
    for item in items:
        cursor.execute('''
            INSERT INTO invoice_items (invoice_id, item_description, dn, da, size, item_price, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (id, item['description'], item['dn'], item['da'], item['size'], item['price'], item['quantity']))
    
    conn.commit()
    conn.close()

def rechnungen_abrufen():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.id, i.client_name, i.client_email, i.invoice_date, i.total
        FROM invoices i
        ORDER BY i.invoice_date DESC
    ''')
    rechnungen = cursor.fetchall()
    conn.close()
    return rechnungen

def pdf_generieren(rechnungsdaten):
    pdf_dateiname = f"Rechnung_{rechnungsdaten['client_name']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    dok = SimpleDocTemplate(pdf_dateiname, pagesize=letter)
    elemente = []

    stile = getSampleStyleSheet()
    elemente.append(Paragraph("Rechnung", stile['Title']))
    elemente.append(Paragraph(f"Datum: {rechnungsdaten['invoice_date']}", stile['Normal']))
    elemente.append(Paragraph(f"Kunde: {rechnungsdaten['client_name']}", stile['Normal']))
    elemente.append(Paragraph(f"E-Mail: {rechnungsdaten['client_email']}", stile['Normal']))

    daten = [
        ['Artikel', 'DN', 'DA', 'Dämmdicke', 'Preis', 'Menge', 'Gesamt']
    ]
    for item in rechnungsdaten['items']:
        daten.append([
            item['description'],
            str(item['dn']) if item['dn'] is not None else '',
            str(item['da']) if item['da'] is not None else '',
            str(item['size']) if item['size'] is not None else '',
            f"€{item['price']:.2f}",
            str(item['quantity']),
            f"€{item['price'] * item['quantity']:.2f}"
        ])
    daten.append(['', '', '', '', '', 'Gesamt', f"€{rechnungsdaten['total']:.2f}"])

    tabelle = Table(daten)
    tabelle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elemente.append(tabelle)
    dok.build(elemente)
    return pdf_dateiname
    
def main(page: ft.Page):
    initialize_database()
    page.title = "Rechnungs-App"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.fonts = {
        "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf"
    }
    page.theme = ft.Theme(font_family="Roboto")
    page.adaptive = True
    
    def build_ui():
        global client_name_dropdown, client_email_dropdown
        bauteil_values = get_unique_bauteil_values()
        logging.info(f"Geladene Bauteil-Werte: {bauteil_values}")
        customer_names = get_unique_customer_names()
        customer_emails = get_unique_customer_emails()
        dn_da_pairs = get_unique_dn_da_pairs()

        client_name_dropdown = ft.Dropdown(
            label="Kundenname",
            width=300,
            options=[ft.dropdown.Option("Neuer Kunde")] + [ft.dropdown.Option(name) for name in customer_names],
            on_change=lambda _: toggle_name_entry()
        )
        client_name_entry = ft.TextField(label="Neuer Kundenname", width=300, visible=False, adaptive=True)

        client_email_dropdown = ft.Dropdown(
            label="Kunden-E-Mail",
            width=300,
            options=[ft.dropdown.Option("Neue E-Mail")] + [ft.dropdown.Option(email) for email in customer_emails],
            on_change=lambda _: toggle_email_entry()
        )
        client_email_entry = ft.TextField(label="Neue Kunden-E-Mail", width=300, visible=False, adaptive=True)

        def toggle_name_entry():
            if client_name_dropdown.value == "Neuer Kunde":
                client_name_entry.visible = True
            else:
                client_name_entry.visible = False
            page.update()

        def toggle_email_entry():
            if client_email_dropdown.value == "Neue E-Mail":
                client_email_entry.visible = True
            else:
                client_email_entry.visible = False
            page.update()

        items = []
        items_container = ft.Column()
        gesamtpreis_text = ft.Text("Gesamtpreis: €0.00", size=20)

        def update_gesamtpreis():
            total = sum(
                float(item["price"].value) * int(item["quantity"].value)
                for item in items
                if item["price"].value and item["quantity"].value
            )
            gesamtpreis_text.value = f"Gesamtpreis: €{total:.2f}"
            page.update()

        def add_item():
            bauteil_values = get_unique_bauteil_values()
            
            new_item = {
                "description": ft.Dropdown(
                    label="Artikelbeschreibung",
                    width=200,
                    options=[ft.dropdown.Option(b) for b in bauteil_values]
                ),
                "dn": ft.Dropdown(
                    label="DN",
                    width=100,
                    visible=False
                ),
                "da": ft.Dropdown(
                    label="DA",
                    width=100,
                    visible=False
                ),
                "size": ft.Dropdown(
                    label="Dämmdicke",
                    width=100
                ),
                "price": ft.TextField(
                    label="Preis",
                    width=100,
                    read_only=True,
                    filled=True,
                    bgcolor=ft.colors.GREY_200
                ),
                "quantity": ft.TextField(label="Menge", width=100, value="1")
            }

            def update_item_options(changed_field):
                bauteil = new_item["description"].value
                selected_dn = new_item["dn"].value
                selected_da = new_item["da"].value
                selected_size = new_item["size"].value

                if bauteil:
                    available_options = get_available_options(bauteil)
                    
                    def size_sort_key(x):
                        try:
                            return float(x.split('-')[0].strip().rstrip('mm'))
                        except ValueError:
                            return 0

                    # Update DN and DA options
                    dn_options = sorted(set(d[0] for d in available_options if len(d) > 0 and d[0] != 0))
                    new_item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
                    new_item["dn"].visible = bool(dn_options)

                    da_options = sorted(set(d[1] for d in available_options if len(d) > 1 and d[1] != 0))
                    new_item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
                    new_item["da"].visible = bool(da_options)

                    if changed_field == "description":
                        new_item["dn"].value = None
                        new_item["da"].value = None
                        new_item["size"].value = None
                    elif changed_field == "dn":
                        new_item["da"].value = None
                        new_item["size"].value = None
                    elif changed_field == "da":
                        new_item["size"].value = None

                    # Update size options based on current selection
                    if changed_field in ["description", "dn", "da"]:
                        filtered_options = available_options
                        if selected_dn:
                            filtered_options = [opt for opt in filtered_options if opt[0] == float(selected_dn)]
                        if selected_da:
                            filtered_options = [opt for opt in filtered_options if opt[1] == float(selected_da)]
                        
                        size_options = sorted(set(d[2] for d in filtered_options if len(d) > 2 and get_price(bauteil, d[0], d[1], d[2]) is not None), key=size_sort_key)
                        new_item["size"].options = [ft.dropdown.Option(value) for value in size_options]
                        print(f"Debug: Verfügbare Größenoptionen: {size_options}")

                    elif changed_field == "size":
                        matching_dn_da = [(dn, da) for dn, da, size in available_options if size == selected_size]
                        if matching_dn_da:
                            dn, da = matching_dn_da[0]
                            new_item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                            new_item["da"].value = f"{da:.1f}"

                print(f"Debug: Werte nach Aktualisierung - Bauteil: {bauteil}, DN: {new_item['dn'].value}, DA: {new_item['da'].value}, Größe: {new_item['size'].value}")
                update_item_price()

            def update_item_price():
                bauteil = new_item["description"].value
                dn = new_item["dn"].value
                da = new_item["da"].value
                size = new_item["size"].value
                print(f"Debug: update_price aufgerufen mit Bauteil: {bauteil}, DN: {dn}, DA: {da}, Größe: {size}")
                
                if bauteil and size:
                    dn_value = float(dn) if dn else 0
                    da_value = float(da) if da else 0
                    price = get_price(bauteil, dn_value, da_value, size)
                    if price is not None:
                        new_item["price"].value = f"{price:.2f}"
                        print(f"Debug: Neuer Preis berechnet: {price:.2f}")
                    else:
                        new_item["price"].value = ""
                        print(f"Debug: Kein Preis gefunden für Bauteil: {bauteil}, DN: {dn_value}, DA: {da_value}, Größe: {size}")
                else:
                    new_item["price"].value = ""
                    print("Debug: Nicht genug Informationen für Preisberechnung")
                new_item["price"].update()
                update_gesamtpreis()
                print(f"Debug: Preisaktualisierung abgeschlossen. Neuer Preis: {new_item['price'].value}")

            def update_item_price():
                bauteil = new_item["description"].value
                dn = new_item["dn"].value
                da = new_item["da"].value
                size = new_item["size"].value
                print(f"Debug: update_price aufgerufen mit Bauteil: {bauteil}, DN: {dn}, DA: {da}, Größe: {size}")
                
                if bauteil and size:
                    dn_value = float(dn) if dn else 0
                    da_value = float(da) if da else 0
                    price = get_price(bauteil, dn_value, da_value, size)
                    if price is not None:
                        new_item["price"].value = f"{price:.2f}"
                        print(f"Debug: Neuer Preis berechnet: {price:.2f}")
                    else:
                        new_item["price"].value = ""
                        print(f"Debug: Kein Preis gefunden für Bauteil: {bauteil}, DN: {dn_value}, DA: {da_value}, Größe: {size}")
                else:
                    new_item["price"].value = ""
                    print("Debug: Nicht genug Informationen für Preisberechnung")
                new_item["price"].update()
                update_gesamtpreis()
                print(f"Debug: Preisaktualisierung abgeschlossen. Neuer Preis: {new_item['price'].value}")

            new_item["description"].on_change = lambda _: update_item_options("description")
            new_item["dn"].on_change = lambda _: update_item_options("dn")
            new_item["da"].on_change = lambda _: update_item_options("da")
            new_item["size"].on_change = lambda _: update_item_options("size")
            new_item["quantity"].on_change = lambda _: update_gesamtpreis()

            items.append(new_item)
            items_container.controls.append(
                ft.Row([
                    new_item["description"],
                    new_item["dn"],
                    new_item["da"],
                    new_item["size"],
                    new_item["price"],
                    new_item["quantity"],
                    ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _, item=new_item: remove_item(item))
                ])
            )
            page.update()

        def remove_item(item):
            items.remove(item)
            items_container.controls = [
                control for control in items_container.controls
                if control.controls[0] != item["description"]
            ]
            update_gesamtpreis()
            page.update()
        
        def calculate_total():
            total = sum(
                float(item["price"].value) * int(item["quantity"].value)
                for item in items
                if item["price"].value and item["quantity"].value
            )
            return total
        
        aktuelle_rechnung_id = None
        
        def rechnung_absenden(e):
            if not client_name_dropdown.value or not client_email_dropdown.value or not items:
                page.snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
                page.overlay.append(page.snack_bar)
                page.snack_bar.open = True
                page.update()
                return
            
            try:
                total = calculate_total()
                rechnungsdaten = {
                    'client_name': client_name_dropdown.value if client_name_dropdown.value != "Neuer Kunde" else client_name_entry.value,
                    'client_email': client_email_dropdown.value if client_email_dropdown.value != "Neue E-Mail" else client_email_entry.value,
                    'invoice_date': datetime.now().strftime('%Y-%m-%d'),
                    'total': total,
                    'items': [
                        {
                            'description': item["description"].value,
                            'dn': item["dn"].value,
                            'da': item["da"].value,
                            'size': item["size"].value,
                            'price': float(item["price"].value),
                            'quantity': int(item["quantity"].value)
                        }
                        for item in items
                        if item["description"].value and item["price"].value and item["quantity"].value
                    ]
                }
                
                if not rechnungsdaten['items']:
                    page.snack_bar = ft.SnackBar(content=ft.Text("Bitte fügen Sie mindestens einen gültigen Artikel hinzu"))
                    page.overlay.append(page.snack_bar)
                    page.snack_bar.open = True
                    page.update()
                    return
                
                rechnung_einfuegen(**rechnungsdaten)
                
                # Aktualisiere die Dropdown-Menüs
                update_customer_dropdowns()
                
                # Clear fields
                client_name_dropdown.value = None
                client_email_dropdown.value = None
                client_name_entry.value = ""
                client_email_entry.value = ""
                items.clear()
                items_container.controls.clear()
                add_item()
                
                page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung erfolgreich erstellt!"))
                page.overlay.append(page.snack_bar)
                page.snack_bar.open = True
                page.update()
            except ValueError:
                page.snack_bar = ft.SnackBar(content=ft.Text("Ungültiger Preis oder Menge"))
                page.overlay.append(page.snack_bar)
                page.snack_bar.open = True
                page.update()
        
        def rechnungen_anzeigen(e):
            rechnungen = rechnungen_abrufen()
            rechnungsliste = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Kunde"), numeric=False),
                    ft.DataColumn(ft.Text("Datum"), numeric=False),
                    ft.DataColumn(ft.Text("Gesamt"), numeric=True),
                    ft.DataColumn(ft.Text("Aktionen"), numeric=False),
                ],
                rows=[],
                column_spacing=50,
                horizontal_lines=ft.border.BorderSide(1, ft.colors.GREY_400),
            )
            
            for rechnung in rechnungen:
                rechnungsliste.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(rechnung[1])),  # Kundenname
                            ft.DataCell(ft.Text(rechnung[3])),  # Datum
                            ft.DataCell(ft.Text(f"€{rechnung[4]:.2f}")),  # Gesamt
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.icons.EDIT,
                                        tooltip="Rechnung bearbeiten",
                                        on_click=lambda _, id=rechnung[0]: rechnung_bearbeiten(id)
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.PICTURE_AS_PDF,
                                        tooltip="PDF neu generieren",
                                        on_click=lambda _, id=rechnung[0]: pdf_neu_generieren_und_anzeigen(id)
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.DELETE,
                                        tooltip="Rechnung löschen",
                                        on_click=lambda _, id=rechnung[0]: rechnung_loeschen_bestaetigen(id)
                                    )
                                ])
                            )
                        ]
                    )
                )
            
            def close_dialog(dialog):
                dialog.open = False
                page.update()

            # Einbetten der Rechnungsliste in einen ListView
            scrollable_content = ft.ListView(
                controls=[rechnungsliste],
                expand=1,
                spacing=10,
                padding=20,
                auto_scroll=True
            )

            rechnungs_dialog = ft.AlertDialog(
                title=ft.Text("Vorhandene Rechnungen"),
                content=ft.Container(
                    content=scrollable_content,
                    width=800,
                    height=500,
                ),
                actions=[
                    ft.TextButton("Schließen", on_click=lambda _: close_dialog(rechnungs_dialog))
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            page.dialog = rechnungs_dialog
            rechnungs_dialog.open = True
            page.update()

        def rechnung_bearbeiten(rechnung_id):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.id, i.client_name, i.client_email, i.invoice_date, i.total,
                       ii.item_description, ii.dn, ii.da, ii.size, ii.item_price, ii.quantity
                FROM invoices i
                JOIN invoice_items ii ON i.id = ii.invoice_id
                WHERE i.id = ?
            ''', (rechnung_id,))
            invoice_items = cursor.fetchall()
            conn.close()

            if not invoice_items:
                print(f"No invoice found with id {rechnung_id}")
                return

            invoice_data = invoice_items[0]
            
            # Clear existing items
            items.clear()
            items_container.controls.clear()

            # Set client name and email
            client_name_dropdown.value = invoice_data[1]  # client_name
            client_email_dropdown.value = invoice_data[2]  # client_email

            def update_gesamtpreis():
                total = sum(
                    float(item["price"].value) * float(item["quantity"].value)
                    for item in items
                    if item["price"].value and item["quantity"].value
                )
                gesamtpreis_text.value = f"Gesamtpreis: €{total:.2f}"
                page.update()

            def create_item(item_data):
                bauteil = item_data[5]  # item_description
                dn = item_data[6]
                da = item_data[7]
                size = item_data[8]

                available_options = get_available_options(bauteil)

                # Prepare options for DN, DA, and size
                dn_options = sorted(set(d[0] for d in available_options if len(d) > 0 and d[0] != 0))
                da_options = sorted(set(d[1] for d in available_options if len(d) > 1 and d[1] != 0))
                size_options = sorted(set(d[2] for d in available_options if len(d) > 2), key=lambda x: float(x.rstrip('mm')))

                new_item = {
                    "description": ft.Dropdown(
                        label="Artikelbeschreibung",
                        width=200,
                        options=[ft.dropdown.Option(b) for b in bauteil_values],
                        value=bauteil
                    ),
                    "dn": ft.Dropdown(
                        label="DN",
                        width=100,
                        visible=bool(dn_options),
                        options=[ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options],
                        value=f"{dn:.0f}" if dn is not None and float(dn).is_integer() else f"{dn}" if dn is not None else None,
                    ),
                    "da": ft.Dropdown(
                        label="DA",
                        width=100,
                        visible=bool(da_options),
                        options=[ft.dropdown.Option(f"{da:.1f}") for da in da_options],
                        value=f"{da:.1f}" if da is not None else None,
                    ),
                    "size": ft.Dropdown(
                        label="Dämmdicke",
                        width=100,
                        options=[ft.dropdown.Option(str(size)) for size in size_options],
                        value=str(size) if size is not None else None,
                    ),
                    "price": ft.TextField(
                        label="Preis",
                        width=100,
                        value=f"{item_data[9]:.2f}",
                        read_only=True,
                        filled=True,
                        bgcolor=ft.colors.GREY_200,  # oder eine andere Farbe Ihrer Wahl
                    ),
                    "quantity": ft.TextField(label="Menge", width=100, value=str(item_data[10]))
                }

                def update_item_options(changed_field):
                    bauteil = new_item["description"].value
                    selected_dn = new_item["dn"].value
                    selected_da = new_item["da"].value
                    selected_size = new_item["size"].value

                    if bauteil:
                        available_options = get_available_options(bauteil)
                        
                        # Update size options
                        size_options = sorted(set(d[2] for d in available_options if len(d) > 2), key=lambda x: float(x.rstrip('mm')))
                        new_item["size"].options = [ft.dropdown.Option(str(value)) for value in size_options]
                        
                        # Update DN and DA options
                        dn_options = sorted(set(d[0] for d in available_options if len(d) > 0 and d[0] != 0))
                        new_item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
                        new_item["dn"].visible = bool(dn_options)

                        da_options = sorted(set(d[1] for d in available_options if len(d) > 1 and d[1] != 0))
                        new_item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
                        new_item["da"].visible = bool(da_options)

                        if changed_field == "size":
                            # Aktualisiere DN und DA basierend auf der ausgewählten Größe
                            matching_dn_da = [(dn, da) for dn, da, size in available_options if size == selected_size]
                            if matching_dn_da:
                                dn, da = matching_dn_da[0]
                                new_item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                                new_item["da"].value = f"{da:.1f}"
                            print(f"Debug: Größe geändert zu {selected_size}, DN: {new_item['dn'].value}, DA: {new_item['da'].value}")
                        elif changed_field in ["dn", "da"]:
                            # Update other fields based on the changed field
                            if changed_field == "dn" and selected_dn:
                                matching_da = [d[1] for d in available_options if len(d) > 1 and d[0] == float(selected_dn)]
                                if matching_da:
                                    new_item["da"].value = f"{matching_da[0]:.1f}"
                            elif changed_field == "da" and selected_da:
                                matching_dn = [d[0] for d in available_options if len(d) > 1 and d[1] == float(selected_da)]
                                if matching_dn:
                                    new_item["dn"].value = f"{matching_dn[0]:.0f}" if float(matching_dn[0]).is_integer() else f"{matching_dn[0]}"
                            
                            if selected_dn and selected_da:
                                matching_size = [d[2] for d in available_options if len(d) > 2 and d[0] == float(selected_dn) and d[1] == float(selected_da)]
                                if matching_size:
                                    new_item["size"].value = str(matching_size[0])

                    print(f"Debug: Werte nach Aktualisierung - Bauteil: {bauteil}, DN: {new_item['dn'].value}, DA: {new_item['da'].value}, Größe: {new_item['size'].value}")
                    update_item_price()

                new_item["description"].on_change = lambda _: update_item_options("description")
                new_item["dn"].on_change = lambda _: update_item_options("dn")
                new_item["da"].on_change = lambda _: update_item_options("da")
                new_item["size"].on_change = lambda _: update_item_options("size")

                def update_item_price():
                    bauteil = new_item["description"].value
                    dn = new_item["dn"].value
                    da = new_item["da"].value
                    size = new_item["size"].value
                    print(f"Debug (rechnung_bearbeiten): Preisaktualisierung gestartet für Bauteil: {bauteil}, DN: {dn}, DA: {da}, Größe: {size}")
                    if bauteil and size:
                        price = get_price(bauteil, float(dn) if dn else 0, float(da) if da else 0, size)
                        if price is not None:
                            new_item["price"].value = f"{price:.2f}"
                            print(f"Debug (rechnung_bearbeiten): Neuer Preis berechnet: {price:.2f}")
                        else:
                            new_item["price"].value = ""
                            print("Debug (rechnung_bearbeiten): Kein Preis gefunden")
                    else:
                        print("Debug (rechnung_bearbeiten): Nicht genug Informationen für Preisberechnung")
                    update_gesamtpreis()
                    page.update()
                    print("Debug (rechnung_bearbeiten): Preisaktualisierung abgeschlossen")

                new_item["description"].on_change = lambda _: update_item_options("description")
                new_item["dn"].on_change = lambda _: update_item_options("dn")
                new_item["da"].on_change = lambda _: update_item_options("da")
                new_item["size"].on_change = lambda _: update_item_options("size")
                new_item["quantity"].on_change = lambda _: update_gesamtpreis()

                # Add update_item_options to the new_item dictionary
                new_item["update_options"] = update_item_options

                return new_item

            for item_data in invoice_items:
                new_item = create_item(item_data)
                items.append(new_item)
                items_container.controls.append(
                    ft.Row([
                        new_item["description"],
                        new_item["dn"],
                        new_item["da"],
                        new_item["size"],
                        new_item["price"],
                        new_item["quantity"],
                        ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _, item=new_item: remove_item(item))
                    ])
                )

                # Initialize options for the item
                new_item["update_options"]("description")  # Call this instead of update_item_options("description")
            
            def neue_rechnung_erstellen(e):
                # Clear all fields and reset the form
                client_name_dropdown.value = None
                client_email_dropdown.value = None
                client_name_entry.value = ""
                client_email_entry.value = ""
                items.clear()
                items_container.controls.clear()
                add_item()
                absenden_btn.text = "Rechnung absenden"
                absenden_btn.on_click = rechnung_absenden
                gesamtpreis_text.value = "Gesamtpreis: €0.00"
                
                # Remove the "Neue Rechnung erstellen" button
                if main_column.controls and isinstance(main_column.controls[0], ft.ElevatedButton):
                    main_column.controls.pop(0)
                
                page.update()

            # Create the "Neue Rechnung erstellen" button
            neue_rechnung_btn = ft.ElevatedButton(
                text="Neue Rechnung erstellen",
                on_click=neue_rechnung_erstellen
            )

            # Modify the submit button to update
            absenden_btn.text = "Rechnung aktualisieren"
            absenden_btn.on_click = lambda _: update_rechnung(rechnung_id)
            
            # Add the new button to the main column only if it's not already there
            if not main_column.controls or not isinstance(main_column.controls[0], ft.ElevatedButton):
                main_column.controls.insert(0, neue_rechnung_btn)
            
            update_gesamtpreis()
            page.update()

        def update_rechnung(rechnung_id):
            if not client_name_dropdown.value or not client_email_dropdown.value or not items:
                page.snack_bar = ft.SnackBar(content=ft.Text("Bitte füllen Sie alle Felder aus"))
                page.overlay.append(page.snack_bar)
                page.snack_bar.open = True
                page.update()
                return
            
            try:
                total = calculate_total()
                rechnungsdaten = {
                    'id': rechnung_id,
                    'client_name': client_name_dropdown.value if client_name_dropdown.value != "Neuer Kunde" else client_name_entry.value,
                    'client_email': client_email_dropdown.value if client_email_dropdown.value != "Neue E-Mail" else client_email_entry.value,
                    'invoice_date': datetime.now().strftime('%Y-%m-%d'),
                    'total': total,
                    'items': [
                        {
                            'description': item["description"].value,
                            'dn': item["dn"].value,
                            'da': item["da"].value,
                            'size': item["size"].value,
                            'price': float(item["price"].value),
                            'quantity': int(item["quantity"].value)
                        }
                        for item in items
                        if item["description"].value and item["price"].value and item["quantity"].value
                    ]
                }
                
                if not rechnungsdaten['items']:
                    page.snack_bar = ft.SnackBar(content=ft.Text("Bitte fügen Sie mindestens einen gültigen Artikel hinzu"))
                    page.overlay.append(page.snack_bar)
                    page.snack_bar.open = True
                    page.update()
                    return
                
                rechnung_aktualisieren(**rechnungsdaten)
                
                # Aktualisiere die Dropdown-Menüs
                update_customer_dropdowns()
                
                # Clear fields and reset form
                client_name_dropdown.value = None
                client_email_dropdown.value = None
                client_name_entry.value = ""
                client_email_entry.value = ""
                items.clear()
                items_container.controls.clear()
                add_item()
                absenden_btn.text = "Rechnung absenden"
                absenden_btn.on_click = rechnung_absenden
                
                page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung erfolgreich aktualisiert!"))
                page.overlay.append(page.snack_bar)
                page.snack_bar.open = True
                page.update()
            except ValueError:
                page.snack_bar = ft.SnackBar(content=ft.Text("Ungültiger Preis oder Menge"))
                page.overlay.append(page.snack_bar)
                page.snack_bar.open = True
                page.update()

        def pdf_neu_generieren(rechnung_id):
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Fetch invoice details
            cursor.execute('''
                SELECT * FROM invoices WHERE id = ?
            ''', (rechnung_id,))
            invoice = cursor.fetchone()
            
            # Fetch invoice items
            cursor.execute('''
                SELECT * FROM invoice_items WHERE invoice_id = ?
            ''', (rechnung_id,))
            items = cursor.fetchall()
            
            conn.close()
            
            if invoice:
                rechnungsdaten = {
                    'client_name': invoice[1],
                    'client_email': invoice[2],
                    'invoice_date': invoice[3],
                    'total': invoice[4],
                    'items': [
                        {
                            'description': item[2],
                            'dn': item[3],
                            'da': item[4],
                            'size': item[5],
                            'price': item[6],
                            'quantity': item[7]
                        } for item in items
                    ]
                }
                
                pdf_dateiname = pdf_generieren(rechnungsdaten)
                return f"PDF neu generiert: {pdf_dateiname}"
            else:
                return "Rechnung nicht gefunden"

        def pdf_neu_generieren_und_anzeigen(id):
            result = pdf_neu_generieren(id)
            page.snack_bar = ft.SnackBar(content=ft.Text(result))
            page.overlay.append(page.snack_bar)
            page.snack_bar.open = True
            page.update()

        def rechnung_loeschen_bestaetigen(rechnung_id):
            def delete_confirmed(e):
                if rechnung_loeschen(rechnung_id):
                    page.snack_bar = ft.SnackBar(content=ft.Text("Rechnung erfolgreich gelöscht"))
                    page.overlay.append(page.snack_bar)
                    page.snack_bar.open = True
                    page.dialog.open = False
                    rechnungen_anzeigen(None)  # Refresh the invoice list
                else:
                    page.snack_bar = ft.SnackBar(content=ft.Text("Fehler beim Löschen der Rechnung"))
                    page.overlay.append(page.snack_bar)
                    page.snack_bar.open = True
                page.update()

            confirm_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Rechnung löschen"),
                content=ft.Text("Sind Sie sicher, dass Sie diese Rechnung löschen möchten?"),
                actions=[
                    ft.TextButton("Abbrechen", on_click=lambda _: close_dialog(confirm_dialog)),
                    ft.TextButton("Löschen", on_click=delete_confirmed),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            def close_dialog(dialog):
                dialog.open = False   
                page.update()




            page.dialog = confirm_dialog
            confirm_dialog.open = True
            page.update()

        absenden_btn = ft.FilledButton(text="Rechnung absenden", on_click=rechnung_absenden, adaptive=True)
        rechnungen_anzeigen_btn = ft.OutlinedButton(text="Vorhandene Rechnungen anzeigen", on_click=rechnungen_anzeigen, adaptive=True)
        add_item_button = ft.ElevatedButton("Artikel hinzufügen", on_click=lambda _: add_item(), adaptive=True)
        
        main_column = ft.Column([
            client_name_dropdown,
            client_name_entry,
            client_email_dropdown,
            client_email_entry,
            add_item_button,
            items_container,
            gesamtpreis_text,
            ft.Row([absenden_btn, rechnungen_anzeigen_btn])
        ], scroll=ft.ScrollMode.ALWAYS)  # Ermöglicht vertikales Scrollen
        
        # Fügen Sie einen horizontalen ScrollView hinzu
        scrollable_view = ft.Row(
            [main_column],
            scroll=ft.ScrollMode.ALWAYS,  # Ermöglicht horizontales Scrollen
            expand=True,
        )
        
        # Add an initial empty item
        add_item()
        
        return scrollable_view

    def route_change(route):
        page.views.clear()
        page.views.append(
            ft.View(
                "/",
                [
                    build_ui()
                ],
            )
        )
        page.update()

    page.on_route_change = route_change
    page.go('/')

def rechnung_loeschen(rechnung_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Delete invoice items first due to foreign key constraint
        cursor.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (rechnung_id,))
        # Then delete the invoice
        cursor.execute('DELETE FROM invoices WHERE id = ?', (rechnung_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_unique_customers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT client_name, client_email FROM invoices')
    customers = cursor.fetchall()
    conn.close()
    return customers

def get_unique_customer_names():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT client_name FROM invoices ORDER BY client_name')
    names = [row[0] for row in cursor.fetchall() if row[0]]  # Filtere leere Namen
    conn.close()
    return names

def get_unique_customer_emails():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT client_email FROM invoices ORDER BY client_email')
    emails = [row[0] for row in cursor.fetchall() if row[0]]  # Filtere leere E-Mails
    conn.close()
    return emails

def get_price(bauteil, dn, da, size):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT value FROM price_list
            WHERE bauteil = ? AND dn = ? AND da = ? AND size = ?
        ''', (bauteil, dn, da, size))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()

def get_available_options(bauteil):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT dn, da, size FROM price_list WHERE bauteil = ? AND value IS NOT NULL AND value != 0', (bauteil,))
    options = cursor.fetchall()
    conn.close()
    return options

def update_options(changed_field, item):
    print(f"Debug: update_options aufgerufen mit changed_field: {changed_field}")
    bauteil = item["description"].value
    selected_dn = item["dn"].value
    selected_da = item["da"].value
    selected_size = item["size"].value
    print(f"Debug: Aktuelle Werte vor Aktualisierung - Bauteil: {bauteil}, DN: {selected_dn}, DA: {selected_da}, Größe: {selected_size}")

    if bauteil:
        available_options = get_available_options(bauteil)
        
        if changed_field == "description":
            # Setze alle Werte zurück
            item["dn"].value = None
            item["da"].value = None
            item["size"].value = None
            
            # Aktualisiere DN-Optionen
            dn_options = sorted(set(dn for dn, _, _ in available_options if dn != 0))
            item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
            item["dn"].visible = bool(dn_options)
            
            # Aktualisiere DA-Optionen
            da_options = sorted(set(da for _, da, _ in available_options if da != 0))
            item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
            item["da"].visible = bool(da_options)
            
            # Aktualisiere Größen-Optionen
            size_options = sorted(set(size for _, _, size in available_options), key=lambda x: float(x.split('-')[0].strip().rstrip('mm')))
            item["size"].options = [ft.dropdown.Option(value) for value in size_options]

        elif changed_field in ["dn", "da"]:
            # Aktualisiere die andere Dimension und die Größe
            if changed_field == "dn" and selected_dn:
                matching_da = sorted(set(da for dn, da, _ in available_options if dn == float(selected_dn) and da != 0))
                item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in matching_da]
                item["da"].value = None
            elif changed_field == "da" and selected_da:
                matching_dn = sorted(set(dn for dn, da, _ in available_options if da == float(selected_da) and dn != 0))
                item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in matching_dn]
                item["dn"].value = None
            
            # Aktualisiere Größen-Optionen basierend auf DN und DA
            if selected_dn and selected_da:
                matching_size = sorted(set(size for dn, da, size in available_options if dn == float(selected_dn) and da == float(selected_da)),
                                       key=lambda x: float(x.split('-')[0].strip().rstrip('mm')))
                item["size"].options = [ft.dropdown.Option(value) for value in matching_size]
                item["size"].value = None

        elif changed_field == "size":
            # Aktualisiere DN und DA basierend auf der ausgewählten Größe
            matching_dn_da = [(dn, da) for dn, da, size in available_options if size == selected_size]
            if matching_dn_da:
                dn, da = matching_dn_da[0]
                item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                item["da"].value = f"{da:.1f}"

    print(f"Debug: Werte nach Aktualisierung - Bauteil: {bauteil}, DN: {item['dn'].value}, DA: {item['da'].value}, Größe: {item['size'].value}")
    
    # Aktualisiere die Dropdown-Menüs
    item["dn"].update()
    item["da"].update()
    item["size"].update()
    
    # Aktualisieren Sie den Preis am Ende der Funktion
    update_price(item)

def update_price(item):
    bauteil = item["description"].value
    dn = item["dn"].value
    da = item["da"].value
    size = item["size"].value
    print(f"Debug: update_price aufgerufen mit Bauteil: {bauteil}, DN: {dn}, DA: {da}, Größe: {size}")
    
    if bauteil and size:
        dn_value = float(dn) if dn else 0
        da_value = float(da) if da else 0
        price = get_price(bauteil, dn_value, da_value, size)
        if price is not None:
            item["price"].value = f"{price:.2f}"
            print(f"Debug: Neuer Preis berechnet: {price:.2f}")
        else:
            item["price"].value = ""
            print(f"Debug: Kein Preis gefunden für Bauteil: {bauteil}, DN: {dn_value}, DA: {da_value}, Größe: {size}")
    else:
        item["price"].value = ""
        print("Debug: Nicht genug Informationen für Preisberechnung")
    item["price"].update()
    print(f"Debug: Preisaktualisierung abgeschlossen. Neuer Preis: {item['price'].value}")


def update_customer_dropdowns():
    global client_name_dropdown, client_email_dropdown
    
    # Aktualisiere Kundennamen
    customer_names = get_unique_customer_names()
    client_name_dropdown.options = [ft.dropdown.Option("Neuer Kunde")] + [ft.dropdown.Option(name) for name in customer_names]
    
    # Aktualisiere Kunden-E-Mails
    customer_emails = get_unique_customer_emails()
    client_email_dropdown.options = [ft.dropdown.Option("Neue E-Mail")] + [ft.dropdown.Option(email) for email in customer_emails]
    
    # Anstatt page.update() zu verwenden, aktualisieren wir die Dropdown-Menüs direkt
    client_name_dropdown.update()
    client_email_dropdown.update()

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)