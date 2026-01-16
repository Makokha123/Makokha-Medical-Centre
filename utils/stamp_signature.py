"""
Digital Stamp and Signature Generator
Generates dynamic, date-stamped official stamps and signatures for all documents
"""
from datetime import datetime
from markupsafe import Markup

def generate_rubber_stamp(facility_name="Makokha Medical Centre", 
                          location="Nairobi • Kenya",
                          current_date=None,
                          stamp_color="#c0392b",
                          size=200):
    """
    Generate HTML for a dynamic rubber stamp with current date
    
    Args:
        facility_name: Name of the facility (default: Makokha Medical Centre)
        location: Location text (default: Nairobi • Kenya)
        current_date: Date to display (default: today)
        stamp_color: Color of stamp (default: red #c0392b)
        size: Size in pixels (default: 200)
    
    Returns:
        Markup: Safe HTML for rubber stamp
    """
    if current_date is None:
        current_date = datetime.now().strftime('%d %b %Y')
    
    # Split facility name for better display
    name_parts = facility_name.split()
    if len(name_parts) >= 2:
        top_text = name_parts[0]
        center_text = ' '.join(name_parts[1:])
    else:
        top_text = ""
        center_text = facility_name
    
    stamp_html = f"""
    <style>
        .rubber-stamp {{
            width: {size}px;
            height: {size}px;
            border: 4px solid {stamp_color};
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            background: linear-gradient(135deg, rgba(192, 57, 43, 0.1) 0%, rgba(192, 57, 43, 0.05) 100%);
            transform: rotate(-15deg);
            font-family: 'Arial Black', 'Arial Bold', Arial, sans-serif;
            text-align: center;
            padding: 15px;
            box-shadow: 0 0 0 2px {stamp_color} inset;
        }}
        
        .rubber-stamp::before {{
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            border: 2px solid {stamp_color};
            border-radius: 50%;
            top: 4px;
            left: 4px;
            opacity: 0.3;
        }}
        
        .stamp-top {{
            font-size: {size * 0.07}px;
            font-weight: bold;
            color: {stamp_color};
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
            line-height: 1.2;
        }}
        
        .stamp-center {{
            font-size: {size * 0.09}px;
            font-weight: 900;
            color: {stamp_color};
            text-transform: uppercase;
            letter-spacing: 2px;
            margin: 8px 0;
            line-height: 1.1;
        }}
        
        .stamp-date {{
            font-size: {size * 0.055}px;
            font-weight: bold;
            color: {stamp_color};
            margin-top: 5px;
            letter-spacing: 0.5px;
        }}
        
        .stamp-bottom {{
            font-size: {size * 0.045}px;
            color: {stamp_color};
            margin-top: 3px;
            text-transform: uppercase;
        }}
        
        @media print {{
            .rubber-stamp {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
    
    <div class="rubber-stamp">
        <div class="stamp-top">{top_text}</div>
        <div class="stamp-center">{center_text.replace(' ', '<br>')}</div>
        <div class="stamp-date">{current_date}</div>
        <div class="stamp-bottom">{location}</div>
    </div>
    """
    
    return Markup(stamp_html)


def generate_digital_signature(signer_name="Dr. J. Makokha",
                               signer_title="Medical Director",
                               signature_date=None,
                               include_date=True):
    """
    Generate HTML for a digital signature
    
    Args:
        signer_name: Name of person signing
        signer_title: Title/position of signer
        signature_date: Date of signature (default: today)
        include_date: Whether to show signature date
    
    Returns:
        Markup: Safe HTML for signature
    """
    if signature_date is None:
        signature_date = datetime.now().strftime('%d %B %Y')
    
    date_html = f'<div class="signature-date">Signed: {signature_date}</div>' if include_date else ''
    
    signature_html = f"""
    <style>
        .signature-container {{
            display: inline-block;
            position: relative;
            margin: 20px 0;
        }}
        
        .signature-script {{
            font-family: 'Brush Script MT', 'Segoe Script', 'Lucida Handwriting', cursive;
            font-size: 42px;
            color: #1a1a1a;
            font-style: italic;
            transform: rotate(-3deg);
            display: inline-block;
            padding: 0 20px;
            position: relative;
            line-height: 1;
        }}
        
        .signature-script::before {{
            content: '';
            position: absolute;
            bottom: -5px;
            left: 10px;
            right: 10px;
            height: 2px;
            background: linear-gradient(to right, transparent, #1a1a1a 20%, #1a1a1a 80%, transparent);
            opacity: 0.4;
        }}
        
        .signature-title {{
            text-align: center;
            font-size: 11px;
            color: #2c3e50;
            margin-top: 5px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .signature-date {{
            text-align: center;
            font-size: 9px;
            color: #7f8c8d;
            margin-top: 2px;
        }}
        
        @media print {{
            .signature-script {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
    
    <div class="signature-container">
        <div class="signature-script">{signer_name}</div>
        <div class="signature-title">{signer_title}</div>
        {date_html}
    </div>
    """
    
    return Markup(signature_html)


def get_current_stamp_date():
    """Get current date formatted for stamp"""
    return datetime.now().strftime('%d %b %Y')


def get_current_signature_date():
    """Get current date formatted for signature"""
    return datetime.now().strftime('%d %B %Y')
