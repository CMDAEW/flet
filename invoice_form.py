item_count = 0

def add_item(e):
    global item_count
    # Existierender Code zum Hinzufügen eines Artikels...
    
    # Am Ende der Funktion
    item_count += 1
    create_pdf_button.disabled = False
    page.update()

def create_pdf(e):
    global item_count
    if item_count > 0:
        # Existierender Code zur PDF-Erstellung...
    else:
        page.snack_bar = ft.SnackBar(content=ft.Text("Bitte fügen Sie mindestens einen Artikel hinzu, bevor Sie die PDF erstellen."))
        page.snack_bar.open = True
        page.update()

# In der Hauptfunktion, wo die Benutzeroberfläche erstellt wird
create_pdf_button = ft.ElevatedButton("PDF erstellen", on_click=create_pdf, disabled=True)