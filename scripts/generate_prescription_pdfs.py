#!/usr/bin/env python3
"""
Generate sample prescription PDFs from text templates.
Creates realistic medical document PDFs for testing and demo.
All documents are clearly marked as FICTIONAL for demo/testing only.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from pathlib import Path
import sys


def create_prescription_pdf(template_path, output_path):
    """Generate a professional PDF from a prescription text template."""
    
    # Read the template
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
    )
    
    # Container for PDF elements
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=1,  # Center
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6,
        spaceBefore=6,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=4,
        leading=12,
        fontName='Helvetica'
    )
    
    warning_style = ParagraphStyle(
        'Warning',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#c0392b'),
        spaceAfter=3,
        leading=11,
        fontName='Helvetica-Bold'
    )
    
    # Split content into lines and process
    lines = content.split('\n')
    
    in_warning = False
    in_instructions = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines at the start
        if not stripped and not elements:
            continue
        
        # Demo warning header
        if 'FICTIONAL MEDICAL DOCUMENT' in stripped:
            elements.append(Paragraph(
                'FICTIONAL MEDICAL DOCUMENT — FOR DEMO/TESTING ONLY',
                warning_style
            ))
            elements.append(Paragraph('NOT A REAL PRESCRIPTION', warning_style))
            elements.append(Spacer(1, 0.1*inch))
            continue
        
        # Main title
        if stripped == 'PRESCRIPTION':
            elements.append(Paragraph('PRESCRIPTION', title_style))
            elements.append(Spacer(1, 0.15*inch))
            continue
        
        # Section headers
        if stripped in ['PATIENT INFORMATION', 'Rx 1.', 'Rx 2.', 'IMPORTANT INSTRUCTIONS', 'FOLLOW-UP']:
            elements.append(Paragraph(stripped, heading_style))
            elements.append(Spacer(1, 0.05*inch))
            if stripped == 'IMPORTANT INSTRUCTIONS':
                in_warning = True
            continue
        
        # Separator lines
        if '-' * 20 in stripped:
            elements.append(Spacer(1, 0.1*inch))
            continue
        
        # Empty line handling
        if not stripped:
            if elements and not isinstance(elements[-1], Spacer):
                elements.append(Spacer(1, 0.05*inch))
            continue
        
        # Regular content
        if stripped and not stripped.startswith('='):
            if in_warning and any(warn in stripped for warn in ['STOP', 'immediately', 'rash', 'difficulty']):
                elements.append(Paragraph(stripped, warning_style))
            else:
                elements.append(Paragraph(stripped, body_style))
    
    # Add footer
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph(
        '<b>All persons, names, and clinical details in this document are entirely fictional and invented for demonstration purposes only.</b>',
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=1,
            leading=10
        )
    ))
    
    # Build PDF
    doc.build(elements)
    print(f"✓ Created: {output_path}")


def main():
    """Generate all prescription PDFs."""
    
    base_dir = Path(__file__).parent.parent
    templates_dir = base_dir / 'agent' / 'data' / 'templates'
    output_dir = base_dir / 'submission' / 'samples'
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Templates to process
    templates = [
        ('prescription_clear.txt', 'prescription_clear.pdf'),
        ('prescription_ambiguous.txt', 'prescription_ambiguous.pdf'),
    ]
    
    for template_name, output_name in templates:
        template_path = templates_dir / template_name
        output_path = output_dir / output_name
        
        if not template_path.exists():
            print(f"✗ Template not found: {template_path}")
            continue
        
        try:
            create_prescription_pdf(template_path, str(output_path))
        except Exception as e:
            print(f"✗ Error creating {output_name}: {e}")
            return 1
    
    print(f"\n✓ All PDFs generated in: {output_dir}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
