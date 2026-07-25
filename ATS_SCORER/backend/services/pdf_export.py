import io
import logging
from xhtml2pdf import pisa

logger = logging.getLogger('ats_resume_scorer')

def generate_combined_pdf(html_docs: dict[str, str]) -> bytes:
    # Concatenate all HTML reports, inserting page breaks between them
    combined_html = ""
    for name, html_str in html_docs.items():
        combined_html += f'<div style="page-break-after: always;">{html_str}</div>'
    
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(combined_html, dest=pdf_buffer)
    
    if pisa_status.err:
        logger.error(f"xhtml2pdf generation failed with {pisa_status.err} errors")
        raise RuntimeError("PDF generation failed inside xhtml2pdf")
        
    return pdf_buffer.getvalue()