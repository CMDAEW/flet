import csv
import os

# Get the current working directory
current_dir = os.getcwd()

# Construct the paths relative to the current directory
input_file = os.path.join(current_dir, 'assets', 'LV_FILES', 'EP.csv')
output_file = os.path.join(current_dir, 'assets', 'LV_FILES', 'EP_updated.csv')

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