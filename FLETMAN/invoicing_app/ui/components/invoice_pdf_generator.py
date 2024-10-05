from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import os
from datetime import datetime
import logging

def generate_pdf(invoice_data, filename, include_prices=True):
    logging.info(f"Starte PDF-Generierung: {filename}")
    doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Normal_RIGHT', parent=styles['Normal'], alignment=2))
    styles.add(ParagraphStyle(name='Normal_CENTER', parent=styles['Normal'], alignment=1))
    
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
    
    # Rechnungsdetails
    invoice_details = [
        ["Kunde:", invoice_data.get('client_name', '')],
        ["Bestell-Nr.:", invoice_data.get('bestell_nr', '')],
        ["Bestelldatum:", invoice_data.get('bestelldatum', '')],
        ["Baustelle:", invoice_data.get('baustelle', '')],
        ["Anlagenteil:", invoice_data.get('anlagenteil', '')],
        ["Aufmaß-Nr.:", invoice_data.get('aufmass_nr', '')],
        ["Auftrags-Nr.:", invoice_data.get('auftrags_nr', '')],
        ["Ausführungsbeginn:", invoice_data.get('ausfuehrungsbeginn', '')],
        ["Ausführungsende:", invoice_data.get('ausfuehrungsende', '')],
    ]
    details_table = Table(invoice_details, colWidths=[60*mm, 130*mm])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 5*mm))
    
    # Artikelliste
    if include_prices:
        data = [["Pos.", "Artikelbezeichnung", "DN", "DA", "Dämmdicke", "Tätigkeit ID", "Menge", "Einheit", "Einheitspreis", "Gesamtpreis"]]
    else:
        data = [["Pos.", "Artikelbezeichnung", "DN", "DA", "Dämmdicke", "Tätigkeit ID", "Menge", "Einheit"]]
    
    for article in invoice_data['articles']:
        row = [
            article['position'],
            article['artikelbeschreibung'],
            article.get('dn', ''),
            article.get('da', ''),
            article.get('dammdicke', ''),
            article.get('taetigkeit', ''),  # Jetzt die Tätigkeits-ID
            article['quantity'],
            article['einheit'],
        ]
        if include_prices:
            row.extend([article['einheitspreis'], article['zwischensumme']])
        data.append(row)
    
    if include_prices:
        col_widths = [15*mm, 40*mm, 15*mm, 15*mm, 20*mm, 25*mm, 15*mm, 15*mm, 20*mm, 20*mm]
    else:
        col_widths = [15*mm, 50*mm, 20*mm, 20*mm, 25*mm, 30*mm, 15*mm, 15*mm]
    
    articles_table = Table(data, colWidths=col_widths)
    articles_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 3*mm),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('BOTTOMPADDING', (0,1), (-1,-1), 2*mm),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))
    elements.append(articles_table)
    
    if include_prices:
        # Gesamtsumme und Zuschläge
        elements.append(Spacer(1, 5*mm))
        total_price_data = [
            ["Nettobetrag:", f"{invoice_data.get('net_total', 0):.2f} €"],
        ]
        for zuschlag, faktor in invoice_data.get('zuschlaege', []):
            zuschlag_betrag = invoice_data['net_total'] * (faktor - 1)
            total_price_data.append([f"Zuschlag {zuschlag}:", f"{zuschlag_betrag:.2f} €"])
        total_price_data.append(["Gesamtbetrag:", f"{invoice_data.get('total_price', 0):.2f} €"])
        
        total_price_table = Table(total_price_data, colWidths=[150*mm, 40*mm])
        total_price_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (0,-1), 'RIGHT'),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
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
    footer = Paragraph(footer_text, styles['Normal'])
    elements.append(footer)
    
    doc.build(elements)
    logging.info("PDF-Generierung abgeschlossen")