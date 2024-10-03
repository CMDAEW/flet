import csv

input_file = 'FLETMAN/invoicing_app/assets/LV_FILES/EP.csv'
output_file = 'FLETMAN/invoicing_app/assets/LV_FILES/EP_updated.csv'

with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    reader = csv.reader(infile, delimiter=';')
    writer = csv.writer(outfile, delimiter=';')

    # Update header
    header = next(reader)
    new_header = ['Positionsnummer'] + header[2:]
    writer.writerow(new_header)

    # Update data rows
    for row in reader:
        new_row = row[1:]  # Remove the first column (ID)
        writer.writerow(new_row)

print(f"Updated CSV file saved as {output_file}")