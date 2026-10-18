from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate


def build_plan_pdf(places):
    """Export the visitor's current order without requesting external map images."""
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=20 * mm,
                                 leftMargin=20 * mm, topMargin=20 * mm,
                                 bottomMargin=20 * mm, title='BandaraGo - Your one-day plan',
                                 author='BandaraGo')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Stop', parent=styles['Heading2'], spaceBefore=16,
                             spaceAfter=7, keepWithNext=True))
    styles.add(ParagraphStyle('Details', parent=styles['BodyText'], leading=15,
                             spaceAfter=5))
    story = [Paragraph('BandaraGo', styles['Title']),
             Paragraph('Your one-day plan', styles['Heading1']),
             Paragraph(f'{len(places)} stops, in your chosen order.', styles['Details']),
             Paragraph('Distances are approximate straight-line measurements from Bandaragama, '
                       'not road distances or distances between stops. Map links require internet access.',
                       styles['Details'])]
    for number, place in enumerate(places, 1):
        categories = ', '.join(category.name for category in place.categories.all())
        story.append(Paragraph(f'{number}. {escape(place.name)}', styles['Stop']))
        for label, value in [('Categories', categories), ('Location', place.address),
                             ('Distance from Bandaragama', f'{place.distance_km:.1f} km (straight-line)')]:
            if value:
                story.append(Paragraph(f'<b>{label}:</b> {escape(value)}', styles['Details']))
        story.append(Paragraph(f'<link href={quoteattr(place.map_url)} '
                               'color="#0d6efd"><u>Open location in Google Maps</u></link>',
                               styles['Details']))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#6c757d'))
        canvas.drawString(20 * mm, 12 * mm, 'BandaraGo | Your one-day plan')
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f'Page {doc.page}')
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    output.seek(0)
    return output
