from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import os
from datetime import datetime
import logging

def generate_pdf(invoice_data, filename, include_prices=True):
    logging.info(f"Erhaltene Rechnungsdaten: {invoice_data}")
    logging.info(f"Starte PDF-Generierung: {filename}")
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm, bottomMargin=20*mm)
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
        [Image(logo_path, width=50*mm, height=20*mm), 
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

    # Artikelliste
    if include_prices:
        data = [["Pos.", "Artikelbezeichnung", "DN", "DA", "Dämmdicke", "Einheit", "Tätigkeit", "Sonderleistungen", "Einheitspreis", "Menge", "Gesamtpreis"]]
        col_widths = [15*mm, 30*mm, 12*mm, 12*mm, 18*mm, 15*mm, 27*mm, 27*mm, 20*mm, 12*mm, 18*mm]
    else:
        data = [["Pos.", "Artikelbezeichnung", "DN", "DA", "Dämmdicke", "Einheit", "Tätigkeit", "Sonderleistungen", "Menge"]]
        col_widths = [15*mm, 35*mm, 15*mm, 15*mm, 20*mm, 15*mm, 30*mm, 30*mm, 15*mm]
    
    for article in invoice_data['articles']:
        logging.info(f"Verarbeite Artikel: {article}")
        taetigkeit_paragraph = Paragraph(article.get('taetigkeit', ''), small_style)
        sonderleistungen_paragraph = Paragraph(article.get('sonderleistungen', ''), small_style)

        row = [
            article['position'],
            article['artikelbeschreibung'],
            article.get('dn', ''),
            article.get('da', ''),
            article.get('dammdicke', ''),
            article.get('einheit', ''),
            taetigkeit_paragraph,
            sonderleistungen_paragraph,
        ]
        if include_prices:
            row.extend([
                article.get('einheitspreis', ''),
                article.get('quantity', ''),
                article.get('zwischensumme', '')
            ])
        else:
            row.append(article.get('quantity', ''))
        data.append(row)

    logging.info(f"Erstellte Datentabelle: {data}")
    
    articles_table = Table(data, colWidths=col_widths, repeatRows=1)
    articles_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),  # Vertikale Zentrierung
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 3*mm),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('BOTTOMPADDING', (0,1), (-1,-1), 2*mm),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('WORDWRAP', (0,0), (-1,-1), True),  # Aktiviert Zeilenumbruch für alle Zellen
    ]))
    elements.append(articles_table)
    
    # Bemerkung hinzufügen
    if invoice_data.get('bemerkung'):
        elements.append(Spacer(1, 5*mm))
        bemerkung_text = f"Bemerkung: {invoice_data['bemerkung']}"
        bemerkung_paragraph = Paragraph(bemerkung_text, styles['Normal'])
        elements.append(bemerkung_paragraph)
    
    # Zuschläge
    elements.append(Spacer(1, 5*mm))
    zuschlaege_data = [["Zuschläge:"]]
    zuschlaege_summe = 0
    nettobetrag = invoice_data.get('net_total', 0)
    for zuschlag, faktor in invoice_data.get('zuschlaege', []):
        if include_prices:
            zuschlag_betrag = nettobetrag * (float(faktor) - 1)
            zuschlaege_summe += zuschlag_betrag
            zuschlaege_data.append([f"{zuschlag}: {zuschlag_betrag:.2f} €"])
        else:
            zuschlaege_data.append([zuschlag])
    
    zuschlaege_table = Table(zuschlaege_data, colWidths=[180*mm])
    zuschlaege_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
    ]))
    elements.append(zuschlaege_table)
    
    if include_prices:
        # Gesamtsumme
        elements.append(Spacer(1, 5*mm))
        gesamtbetrag = nettobetrag + zuschlaege_summe
        total_price_data = [
            ["Nettobetrag:", f"{nettobetrag:.2f} €"],
            ["Zuschläge:", f"{zuschlaege_summe:.2f} €"],
            ["Gesamtbetrag:", f"{gesamtbetrag:.2f} €"]
        ]
        
        total_price_table = Table(total_price_data, colWidths=[140*mm, 40*mm])
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
    
    # Fußzeile
    elements.append(Spacer(1, 10*mm))
    footer_text = """
    Zahlungsbedingungen: 30 Tage netto
    Bankverbindung: Commerzbank AG • IBAN DE12 2904 0090 0311 3333 00 • BIC COBADEFFXXX
    Geschäftsführer: Dr. Roland Gärber, Steen E. Hansen
    Sitz der Gesellschaft: Bremen • Handelsregister: Amtsgericht Bremen HRB 30731 HB
    Steuernummer: 60 145 14407 • USt-ID: DE 813 770 842
    """
    footer = Paragraph(footer_text, styles['Small'])
    elements.append(footer)
    
    doc.build(elements)
    logging.info("PDF-Generierung abgeschlossen")