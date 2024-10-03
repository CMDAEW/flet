import pandas as pd
import os

def remove_duplicates(input_file='EP.csv', output_file='EP_cleaned.csv', duplicates_file='duplicates_removed.csv'):
    """
    Entfernt doppelte Einträge aus der CSV-Datei basierend auf bestimmten Spalten,
    während die 'ID'-Spalte beibehalten wird. Speichert die bereinigte Datei und die
    entfernten Duplikate separat.
    
    :param input_file: Name der Original-CSV-Datei.
    :param output_file: Name der bereinigten CSV-Datei.
    :param duplicates_file: Name der Datei, die die entfernten Duplikate speichert.
    """
    
    # Überprüfen, ob die Eingabedatei existiert
    if not os.path.isfile(input_file):
        print(f"Fehler: Die Datei '{input_file}' wurde nicht gefunden.")
        return
    
    try:
        # Laden der CSV-Datei in einen DataFrame
        df = pd.read_csv(input_file)
        print("Originale Daten geladen:")
        print(df.head())
    except pd.errors.EmptyDataError:
        print(f"Fehler: Die Datei '{input_file}' ist leer.")
        return
    except pd.errors.ParserError as e:
        print(f"Fehler: Die Datei '{input_file}' konnte nicht korrekt geparst werden.\nDetails: {e}")
        return
    
    # Überprüfen, ob die erforderlichen Spalten vorhanden sind
    required_columns = ['ID', 'Item Number', 'DN', 'DA', 'Size', 'Value', 'Unit', 'Bauteil']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Fehler: Die folgenden erforderlichen Spalten fehlen in der CSV-Datei: {missing_columns}")
        return
    
    # Definieren der Spalten, die zur Duplikaterkennung verwendet werden sollen (ohne 'ID')
    columns_to_check = ['Item Number', 'DN', 'DA', 'Size', 'Value', 'Unit', 'Bauteil']
    
    # Sortieren des DataFrames nach 'ID' in absteigender Reihenfolge, um die höchste 'ID' zu behalten
    df_sorted = df.sort_values(by='ID', ascending=False)
    
    # Identifizieren der Duplikate (doppelte Zeilen basierend auf den definierten Spalten)
    duplicates = df_sorted[df_sorted.duplicated(subset=columns_to_check, keep='first')]
    
    # Entfernen der Duplikate und Beibehalten der Zeile mit der höchsten 'ID'
    df_cleaned = df_sorted.drop_duplicates(subset=columns_to_check, keep='first')
    
    # Anzahl der entfernten Duplikate
    duplicates_removed = len(duplicates)
    print(f"\nAnzahl der entfernten Duplikate: {duplicates_removed}")
    
    # Speichern der bereinigten Daten in eine neue CSV-Datei
    try:
        df_cleaned.to_csv(output_file, index=False)
        print(f"Bereinigte Datei gespeichert als '{output_file}'.")
    except Exception as e:
        print(f"Fehler beim Speichern der bereinigten Datei: {e}")
    
    # Speichern der entfernten Duplikate in eine separate CSV-Datei
    try:
        duplicates.to_csv(duplicates_file, index=False)
        print(f"Duplikate wurden in '{duplicates_file}' gespeichert.")
    except Exception as e:
        print(f"Fehler beim Speichern der Duplikate: {e}")

if __name__ == "__main__":
    remove_duplicates()
