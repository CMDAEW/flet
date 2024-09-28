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
    
    def build_ui():
        customer_names = get_unique_customer_names()
        customer_emails = get_unique_customer_emails()
        bauteil_values = get_unique_bauteil_values()
        dn_da_pairs = get_unique_dn_da_pairs()

        client_name_dropdown = ft.Dropdown(
            label="Kundenname",
            width=300,
            options=[ft.dropdown.Option(name) for name in customer_names] + [ft.dropdown.Option("Neuer Kunde")],
        )
        client_name_entry = ft.TextField(label="Neuer Kundenname", width=300, visible=False)

        client_email_dropdown = ft.Dropdown(
            label="Kunden-E-Mail",
            width=300,
            options=[ft.dropdown.Option(email) for email in customer_emails] + [ft.dropdown.Option("Neue E-Mail")],
        )
        client_email_entry = ft.TextField(label="Neue Kunden-E-Mail", width=300, visible=False)

        def on_client_name_change(e):
            if client_name_dropdown.value == "Neuer Kunde":
                client_name_entry.visible = True
            else:
                client_name_entry.visible = False
            page.update()

        def on_client_email_change(e):
            if client_email_dropdown.value == "Neue E-Mail":
                client_email_entry.visible = True
            else:
                client_email_entry.visible = False
            page.update()

        client_name_dropdown.on_change = on_client_name_change
        client_email_dropdown.on_change = on_client_email_change

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
            item = {
                "description": ft.Dropdown(
                    label="Artikelbeschreibung",
                    width=200,
                    options=[ft.dropdown.Option(bauteil) for bauteil in bauteil_values]
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
                "price": ft.TextField(label="Preis", width=100),
                "quantity": ft.TextField(label="Menge", width=100),
            }

            def update_options(changed_field):
                bauteil = item["description"].value
                selected_dn = item["dn"].value
                selected_da = item["da"].value
                selected_size = item["size"].value

                if bauteil:
                    available_options = get_available_options(bauteil)
                    
                    # Update size options
                    size_options = sorted(set(size for _, _, size in available_options))
                    item["size"].options = [ft.dropdown.Option(value) for value in size_options]
                    
                    # Show/hide DN and DA fields
                    item["dn"].visible = any(dn != 0 for dn, _, _ in available_options)
                    item["da"].visible = any(da != 0 for _, da, _ in available_options)

                    if item["dn"].visible:
                        dn_options = sorted(set(dn for dn, _, _ in available_options if dn != 0))
                        item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]

                    if item["da"].visible:
                        da_options = sorted(set(da for _, da, _ in available_options if da != 0))
                        item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]

                    if changed_field == "description":
                        # Reset DN, DA, and size when description changes
                        item["dn"].value = None
                        item["da"].value = None
                        item["size"].value = None
                    elif changed_field in ["dn", "da", "size"]:
                        # Update other fields based on the changed field
                        if changed_field == "dn" and selected_dn:
                            matching_da = [da for dn, da, _ in available_options if dn == float(selected_dn)]
                            if matching_da:
                                item["da"].value = f"{matching_da[0]:.1f}"
                        elif changed_field == "da" and selected_da:
                            matching_dn = [dn for dn, da, _ in available_options if da == float(selected_da)]
                            if matching_dn:
                                item["dn"].value = f"{matching_dn[0]:.0f}" if float(matching_dn[0]).is_integer() else f"{matching_dn[0]}"
                        
                        if selected_dn and selected_da:
                            matching_size = [size for dn, da, size in available_options if dn == float(selected_dn) and da == float(selected_da)]
                            if matching_size:
                                item["size"].value = matching_size[0]
                        elif changed_field == "size" and selected_size:
                            matching_dn_da = [(dn, da) for dn, da, size in available_options if size == selected_size]
                            if matching_dn_da:
                                dn, da = matching_dn_da[0]
                                item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                                item["da"].value = f"{da:.1f}"

                else:
                    item["dn"].options = []
                    item["da"].options = []
                    item["size"].options = []
                    item["dn"].value = None
                    item["da"].value = None
                    item["size"].value = None
                    item["dn"].visible = False
                    item["da"].visible = False

                update_price()
                page.update()

            def update_price():
                bauteil = item["description"].value
                dn = item["dn"].value
                da = item["da"].value
                size = item["size"].value
                if bauteil and size:
                    price = get_price(bauteil, float(dn) if dn else 0, float(da) if da else 0, size)
                    if price is not None:
                        item["price"].value = f"{price:.2f}"
                    else:
                        item["price"].value = ""
                page.update()

            def on_description_change(e):
                update_options("description")

            def on_dn_change(e):
                update_options("dn")

            def on_da_change(e):
                update_options("da")

            def on_size_change(e):
                update_options("size")

            def on_price_change(e):
                update_gesamtpreis()

            def on_quantity_change(e):
                update_gesamtpreis()

            item["description"].on_change = on_description_change
            item["dn"].on_change = on_dn_change
            item["da"].on_change = on_da_change
            item["size"].on_change = on_size_change
            item["price"].on_change = on_price_change
            item["quantity"].on_change = on_quantity_change

            items.append(item)
            items_container.controls.append(
                ft.Row([
                    item["description"],
                    item["dn"],
                    item["da"],
                    item["size"],
                    item["price"],
                    item["quantity"],
                    ft.IconButton(icon=ft.icons.DELETE, on_click=lambda _: remove_item(item))
                ])
            )
            update_gesamtpreis()
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
                    ft.DataColumn(ft.Text("Kunde")),
                    ft.DataColumn(ft.Text("Datum")),
                    ft.DataColumn(ft.Text("Gesamt")),
                    ft.DataColumn(ft.Text("Aktionen")),
                ],
                rows=[]
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

            rechnungs_dialog = ft.AlertDialog(
                title=ft.Text("Vorhandene Rechnungen"),
                content=ft.Container(
                    content=rechnungsliste,
                    width=700,
                    height=400,
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
                size_options = sorted(set(d[2] for d in available_options if len(d) > 2))

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
                        read_only=True
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
                        size_options = sorted(set(d[2] for d in available_options if len(d) > 2))
                        new_item["size"].options = [ft.dropdown.Option(str(value)) for value in size_options]
                        
                        # Update DN and DA options
                        dn_options = sorted(set(d[0] for d in available_options if len(d) > 0 and d[0] != 0))
                        new_item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]
                        new_item["dn"].visible = bool(dn_options)

                        da_options = sorted(set(d[1] for d in available_options if len(d) > 1 and d[1] != 0))
                        new_item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]
                        new_item["da"].visible = bool(da_options)

                        if changed_field in ["dn", "da", "size"]:
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
                            elif changed_field == "size" and selected_size:
                                matching_dn_da = [(d[0], d[1]) for d in available_options if len(d) > 2 and d[2] == selected_size]
                                if matching_dn_da:
                                    dn, da = matching_dn_da[0]
                                    new_item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                                    new_item["da"].value = f"{da:.1f}"

                    update_item_price()
                    update_gesamtpreis()
                    page.update()

                def update_item_price():
                    bauteil = new_item["description"].value
                    dn = new_item["dn"].value
                    da = new_item["da"].value
                    size = new_item["size"].value
                    if bauteil and size:
                        price = get_price(bauteil, float(dn) if dn else 0, float(da) if da else 0, size)
                        if price is not None:
                            new_item["price"].value = f"{price:.2f}"
                        else:
                            new_item["price"].value = ""
                    update_gesamtpreis()
                    page.update()

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

        absenden_btn = ft.FilledButton(text="Rechnung absenden", on_click=rechnung_absenden)
        rechnungen_anzeigen_btn = ft.OutlinedButton(text="Vorhandene Rechnungen anzeigen", on_click=rechnungen_anzeigen)
        add_item_button = ft.ElevatedButton("Artikel hinzufügen", on_click=lambda _: add_item())
        
        main_column = ft.Column([
            client_name_dropdown,
            client_name_entry,
            client_email_dropdown,
            client_email_entry,
            add_item_button,
            items_container,
            gesamtpreis_text,
            ft.Row([absenden_btn, rechnungen_anzeigen_btn])
        ])
        
        # Add an initial empty item
        add_item()
        
        return main_column

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
    customers = get_unique_customers()
    return sorted(list(set([customer[0] for customer in customers])))

def get_unique_customer_emails():
    customers = get_unique_customers()
    return sorted(list(set([customer[1] for customer in customers])))

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
    try:
        cursor.execute('''
            SELECT DISTINCT dn, da, size FROM price_list
            WHERE bauteil = ? AND value IS NOT NULL
        ''', (bauteil,))
        return cursor.fetchall()
    finally:
        conn.close()

def update_options(changed_field, item):
    bauteil = item["description"].value
    selected_dn = item["dn"].value
    selected_da = item["da"].value
    selected_size = item["size"].value

    if bauteil:
        available_options = get_available_options(bauteil)
        
        # Update size options
        size_options = sorted(set(size for _, _, size in available_options))
        item["size"].options = [ft.dropdown.Option(value) for value in size_options]
        
        # Show/hide DN and DA fields
        item["dn"].visible = any(dn != 0 for dn, _, _ in available_options)
        item["da"].visible = any(da != 0 for _, da, _ in available_options)

        if item["dn"].visible:
            dn_options = sorted(set(dn for dn, _, _ in available_options if dn != 0))
            item["dn"].options = [ft.dropdown.Option(f"{dn:.0f}" if float(dn).is_integer() else f"{dn}") for dn in dn_options]

        if item["da"].visible:
            da_options = sorted(set(da for _, da, _ in available_options if da != 0))
            item["da"].options = [ft.dropdown.Option(f"{da:.1f}") for da in da_options]

        if changed_field == "description":
            # Reset DN, DA, and size when description changes
            item["dn"].value = None
            item["da"].value = None
            item["size"].value = None
        elif changed_field in ["dn", "da", "size"]:
            # Update other fields based on the changed field
            if changed_field == "dn" and selected_dn:
                matching_da = [da for dn, da, _ in available_options if dn == float(selected_dn)]
                if matching_da:
                    item["da"].value = f"{matching_da[0]:.1f}"
            elif changed_field == "da" and selected_da:
                matching_dn = [dn for dn, da, _ in available_options if da == float(selected_da)]
                if matching_dn:
                    item["dn"].value = f"{matching_dn[0]:.0f}" if float(matching_dn[0]).is_integer() else f"{matching_dn[0]}"
            
            if selected_dn and selected_da:
                matching_size = [size for dn, da, size in available_options if dn == float(selected_dn) and da == float(selected_da)]
                if matching_size:
                    item["size"].value = matching_size[0]
            elif changed_field == "size" and selected_size:
                matching_dn_da = [(dn, da) for dn, da, size in available_options if size == selected_size]
                if matching_dn_da:
                    dn, da = matching_dn_da[0]
                    item["dn"].value = f"{dn:.0f}" if float(dn).is_integer() else f"{dn}"
                    item["da"].value = f"{da:.1f}"

    else:
        item["dn"].options = []
        item["da"].options = []
        item["size"].options = []
        item["dn"].value = None
        item["da"].value = None
        item["size"].value = None
        item["dn"].visible = False
        item["da"].visible = False

    def update_price(item, page):
        bauteil = item["description"].value
        dn = item["dn"].value
        da = item["da"].value
        size = item["size"].value
        if bauteil and size:
            price = get_price(bauteil, float(dn) if dn else 0, float(da) if da else 0, size)
            if price is not None:
                item["price"].value = f"{price:.2f}"
            else:
                item["price"].value = ""
        page.update()


def update_price(item):
    bauteil = item["description"].value
    dn = item["dn"].value
    da = item["da"].value
    size = item["size"].value
    if bauteil and size:
        price = get_price(bauteil, float(dn) if dn else 0, float(da) if da else 0, size)
        if price is not None:
            item["price"].value = f"{price:.2f}"
        else:
            item["price"].value = ""
    item.update()

if __name__ == "__main__":
    initialize_database()
    ft.app(target=main)
    