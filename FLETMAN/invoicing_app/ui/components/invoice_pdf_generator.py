from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import os
from datetime import datetime
from reportlab.pdfbase.pdfmetrics import stringWidth
import logging

class InvoiceDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        BaseDocTemplate.__init__(self, filename, **kwargs)
        self.allowSplitting = 0
        template = PageTemplate('normal', [Frame(self.leftMargin, self.bottomMargin, self.width, self.height - 25*mm, id='normal')])
        self.addPageTemplates(template)
    
    def afterPage(self):
        canvas = self.canv
        canvas.saveState()
        
        # Fußzeile
        footer_text_left = """
        Zahlungsbedingungen: 30 Tage netto
        Bankverbindung: Commerzbank AG
        IBAN DE12 2904 0090 0311 3333 00
        BIC COBADEFFXXX
        """
        
        footer_text_right = """
        Geschäftsführer: Dr. Roland Gärber, Steen E. Hansen
        Sitz der Gesellschaft: Bremen
        Handelsregister: Amtsgericht Bremen HRB 30731 HB
        Steuernummer: 60 145 14407 • USt-ID: DE 813 770 842
        """
        
        canvas.setFont("Helvetica", 6)
        
        # Linke Spalte
        textobject_left = canvas.beginText(self.leftMargin, 20*mm)
        for line in footer_text_left.split('\n'):
            textobject_left.textLine(line.strip())
        canvas.drawText(textobject_left)
        
        # Rechte Spalte
        textobject_right = canvas.beginText(self.width/2 + self.leftMargin, 20*mm)
        for line in footer_text_right.split('\n'):
            textobject_right.textLine(line.strip())
        canvas.drawText(textobject_right)
        
        canvas.restoreState()

def calculate_column_widths(table_data, available_width, font_name, font_size):
    num_columns = len(table_data[0])
    min_widths = [0] * num_columns
    
    # Berechne die minimale Breite für jede Spalte
    for row in table_data:
        for i, cell in enumerate(row):
            cell_width = stringWidth(str(cell), font_name, font_size) + 4  # 4 für Padding
            min_widths[i] = max(min_widths[i], cell_width)
    
    total_min_width = sum(min_widths)
    
    if total_min_width <= available_width:
        # Verteile übrigen Platz proportional
        extra_space = available_width - total_min_width
        for i in range(num_columns):
            min_widths[i] += (min_widths[i] / total_min_width) * extra_space
    else:
        # Wenn nicht genug Platz, reduziere proportional
        scale_factor = available_width / total_min_width
        for i in range(num_columns):
            min_widths[i] *= scale_factor
    
    return min_widths

def generate_pdf(invoice_data, filename, include_prices=True):
    logging.info(f"Erhaltene Rechnungsdaten: {invoice_data}")
    logging.info(f"Starte PDF-Generierung: {filename}")
    doc = InvoiceDocTemplate(filename, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm, bottomMargin=20*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Normal_RIGHT', parent=styles['Normal'], alignment=2))
    styles.add(ParagraphStyle(name='Normal_CENTER', parent=styles['Normal'], alignment=1))
    styles.add(ParagraphStyle(name='Small', parent=styles['Normal'], fontSize=8))
    
    # Pfad zum Logo relativ zum Root-Ordner
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                             'assets', 'logos', 'KAE_Logo_RGB_300dpi2.jpg')
    
    # Kopfzeile
    header_data = [
    [Image(logo_path, width=50*mm, height=15*mm), 
     Paragraph("KAEFER Industrie GmbH<br/>Niederlassung Norddeutschland<br/>Standort Bremen", styles['Normal']),
     ""],
    ["", "", Paragraph("Getreidestraße 3<br/>28217 Bremen<br/>Deutschland", styles['Normal_RIGHT'])],
    ["", "", ""],
    ["", Paragraph("<b>Rechnung</b>", styles['Normal_CENTER']), ""]
    ]
    header_table = Table(header_data, colWidths=[60*mm, 70*mm, 60*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('SPAN', (1,3), (2,3)),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10*mm))
    
    # Rechnungsdetails in zwei Spalten
    invoice_details_left = [
    ["Kunde:", invoice_data.get('client_name', '')],
    ["Bestell-Nr.:", invoice_data.get('bestell_nr', '')],
    ["Bestelldatum:", invoice_data.get('bestelldatum', '')],
    ["Baustelle:", invoice_data.get('baustelle', '')],
    ["Anlagenteil:", invoice_data.get('anlagenteil', '')],
    ]
    invoice_details_right = [
    ["Aufmaß-Nr.:", invoice_data.get('aufmass_nr', '')],
    ["Auftrags-Nr.:", invoice_data.get('auftrags_nr', '')],
    ["Ausführungsbeginn:", invoice_data.get('ausfuehrungsbeginn', '')],
    ["Ausführungsende:", invoice_data.get('ausfuehrungsende', '')],
    ]
    details_table = Table([
    [Table(invoice_details_left, colWidths=[40*mm, 50*mm]), Table(invoice_details_right, colWidths=[40*mm, 50*mm])]
    ], colWidths=[90*mm, 90*mm])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1*mm),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 5*mm))
    
    # Definieren Sie einen Stil für die Tätigkeits- und Sonderleistungen-Zelle
    small_style = ParagraphStyle(
    'Small',
    parent=styles['Normal'],
    fontSize=7,
    leading=8,
        alignment=1  # Zentrierte Ausrichtung
    )

    # Definieren Sie einen Stil für Zellen mit Zeilenumbruch
    wrap_style = ParagraphStyle(
        'Wrap',
        parent=styles['Normal'],
        fontSize=6,
        leading=7,
        alignment=1  # Zentrierte Ausrichtung
    )

    # Artikelliste
    columns = ["Lfd.\nNr.", "Pos", "Bauteil", "DN/DA", "Dämm-\ndicke", "Einheit", "Tätigkeit", "Sonderleistungen"]
    if include_prices:
        columns.extend(["Preis", "Menge", "Zwischen-\nsumme"])
    
    table_data = [columns]
    for index, item in enumerate(invoice_data['articles'], start=1):
        dn_da = f"{item.get('dn', '')}/{item.get('da', '')}"
        row = [
            str(index),
            item['position'],
            item['artikelbeschreibung'],
            dn_da,
            item.get('dammdicke', ''),
            item.get('einheit', ''),
            Paragraph(item.get('taetigkeit', '').replace(' / ', '\n'), wrap_style),
            Paragraph(item.get('sonderleistungen', '').replace(', ', '\n'), wrap_style)
        ]
        if include_prices:
            row.extend([
                item.get('einheitspreis', ''),
                item.get('quantity', ''),
                item.get('zwischensumme', '')
            ])
        table_data.append(row)

    logging.info(f"Erstellte Datentabelle: {table_data}")
    
    # Berechnen Sie die verfügbare Breite
    available_width = doc.width - doc.leftMargin - doc.rightMargin

    # Definieren Sie relative Spaltenbreiten
    col_widths = [0.05, 0.08, 0.15, 0.08, 0.08, 0.06, 0.12, 0.15]
    if include_prices:
        col_widths.extend([0.08, 0.07, 0.08])
    col_widths = [w * available_width for w in col_widths]

    # Erstellen Sie die Tabelle mit den berechneten Spaltenbreiten
    articles_table = Table(table_data, repeatRows=1, colWidths=col_widths, splitByRow=True)
    articles_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (1,-1), 4),  # Mehr Puffer für Lfd.Nr. und Pos
        ('RIGHTPADDING', (0,0), (1,-1), 4),  # Mehr Puffer für Lfd.Nr. und Pos
        ('LEFTPADDING', (-1,0), (-1,-1), 4),  # Mehr Puffer für Zwischensumme
        ('RIGHTPADDING', (-1,0), (-1,-1), 4),  # Mehr Puffer für Zwischensumme
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('WORDWRAP', (0,0), (-1,-1), True),
    ]))
    elements.append(articles_table)
    
    # Zuschläge und Bemerkung
    elements.append(Spacer(1, 5*mm))
    
    # Erstellen Sie eine Tabelle mit zwei Spalten: Bemerkung links, Zuschläge rechts
    bemerkung_text = invoice_data.get('bemerkung', '').strip()
    bemerkung_para = Paragraph(f"<b>Bemerkung:</b><br/>{bemerkung_text}", styles['Normal']) if bemerkung_text else None

    zuschlaege_data = []
    zuschlaege_summe = 0
    nettobetrag = invoice_data.get('net_total', 0)
    if invoice_data.get('zuschlaege'):
        zuschlaege_header = ["Zuschläge:"]
        if include_prices:
            zuschlaege_header.append("Betrag:")
        zuschlaege_data.append(zuschlaege_header)
        for zuschlag, faktor in invoice_data['zuschlaege']:
            if include_prices:
                zuschlag_betrag = nettobetrag * (float(faktor) - 1)
                zuschlaege_summe += zuschlag_betrag
                zuschlaege_data.append([zuschlag, f"{zuschlag_betrag:.2f} €"])
            else:
                zuschlaege_data.append([zuschlag])

    if zuschlaege_data:
        zuschlaege_table = Table(zuschlaege_data, colWidths=[80*mm, 40*mm] if include_prices else [120*mm])
        zuschlaege_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('BOTTOMPADDING', (0,0), (-1,0), 1*mm),
            ('TOPPADDING', (0,1), (-1,-1), 0),
            ('BOTTOMPADDING', (0,1), (-1,-1), 0),
        ]))
    else:
        zuschlaege_table = None

    if bemerkung_para or zuschlaege_table:
        combined_table = Table([[bemerkung_para or '', zuschlaege_table or '']], 
                               colWidths=[doc.width/2 - 10*mm, doc.width/2 - 10*mm])
        combined_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
            ('TOPPADDING', (0,0), (-1,-1), 1*mm),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1*mm),
        ]))
        elements.append(combined_table)

    if include_prices:
        # Gesamtsumme
        elements.append(Spacer(1, 5*mm))
        gesamtbetrag = nettobetrag + zuschlaege_summe
        total_price_data = [
            ["Nettobetrag:", f"{nettobetrag:.2f} €"],
            ["Zuschläge:", f"{zuschlaege_summe:.2f} €"],
            ["Gesamtbetrag:", f"{gesamtbetrag:.2f} €"]
        ]
        
        total_price_table = Table(total_price_data, colWidths=[doc.width - 60*mm, 50*mm])
        total_price_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (0,-1), 'RIGHT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
            ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
        ]))
        elements.append(total_price_table)
    
    doc.build(elements)
    logging.info("PDF-Generierung abgeschlossen")
