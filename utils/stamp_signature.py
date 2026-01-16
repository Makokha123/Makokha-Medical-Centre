"""
Digital Stamp and Signature Generator
Generates dynamic, date-stamped official stamps and signatures for all documents
"""
from datetime import datetime
from markupsafe import Markup

def generate_rubber_stamp(facility_name="MAKOKHA MEDICAL CENTRE", 
                          email="makokhamedicalcentre2026@gmail.com",
                          phone1="0741 256 831",
                          phone2="0713 580 997",
                          current_date=None,
                          stamp_color="#2e3192",
                          size=300):
    """
    Generate SVG for a rectangular rubber stamp matching the provided image
    
    Args:
        facility_name: Name of the facility (default: MAKOKHA MEDICAL CENTRE)
        email: Email address
        phone1: First phone number
        phone2: Second phone number
        current_date: Date to display (default: today in format "21 DEC 2025")
        stamp_color: Color of stamp (default: blue #2e3192)
        size: Width in pixels (default: 300)
    
    Returns:
        Markup: Safe HTML/SVG for rubber stamp
    """
    if current_date is None:
        # Format: "21 DEC 2025"
        current_date = datetime.now().strftime('%d %b %Y').upper()
    
    # Calculate proportional dimensions (matching the rectangular stamp image)
    width = size
    height = size * 0.55  # Rectangular ratio
    
    stamp_svg = f"""
    <svg width="{width}" height="{height}" viewBox="0 0 400 220" xmlns="http://www.w3.org/2000/svg" style="background: transparent;">
        <!-- Outer border -->
        <rect x="5" y="5" width="390" height="210" 
              fill="none" 
              stroke="{stamp_color}" 
              stroke-width="6" 
              rx="3"/>
        
        <!-- Inner border -->
        <rect x="12" y="12" width="376" height="196" 
              fill="none" 
              stroke="{stamp_color}" 
              stroke-width="2" 
              rx="2"/>
        
        <!-- Facility name (top) -->
        <text x="200" y="50" 
              font-family="Arial Black, Arial, sans-serif" 
              font-size="32" 
              font-weight="900" 
              fill="{stamp_color}" 
              text-anchor="middle"
              letter-spacing="1">
            {facility_name.split()[0]}
        </text>
        <text x="200" y="80" 
              font-family="Arial Black, Arial, sans-serif" 
              font-size="32" 
              font-weight="900" 
              fill="{stamp_color}" 
              text-anchor="middle"
              letter-spacing="1">
            {' '.join(facility_name.split()[1:])}
        </text>
        
        <!-- Left star -->
        <polygon points="50,110 53,118 62,118 55,124 58,132 50,127 42,132 45,124 38,118 47,118" 
                 fill="{stamp_color}"/>
        
        <!-- Date (center, in red) -->
        <text x="200" y="130" 
              font-family="Arial Black, Arial, sans-serif" 
              font-size="38" 
              font-weight="900" 
              fill="#dc143c" 
              text-anchor="middle"
              letter-spacing="1">
            {current_date}
        </text>
        
        <!-- Right star -->
        <polygon points="350,110 353,118 362,118 355,124 358,132 350,127 342,132 345,124 338,118 347,118" 
                 fill="{stamp_color}"/>
        
        <!-- Email -->
        <text x="200" y="165" 
              font-family="Arial, sans-serif" 
              font-size="18" 
              font-weight="bold" 
              fill="{stamp_color}" 
              text-anchor="middle">
            {email}
        </text>
        
        <!-- Phone numbers -->
        <text x="200" y="190" 
              font-family="Arial, sans-serif" 
              font-size="18" 
              font-weight="bold" 
              fill="{stamp_color}" 
              text-anchor="middle">
            Tel: {phone1} / {phone2}
        </text>
    </svg>
    """
    
    return Markup(stamp_svg)


def generate_digital_signature(signer_name="Makokha",
                               signer_title="Medical Director",
                               signature_date=None,
                               include_date=True):
    """
    Generate SVG for a cursive handwritten-style signature matching the provided image
    
    Args:
        signer_name: Name of person signing (default: Makokha)
        signer_title: Title/position of signer
        signature_date: Date of signature (default: today)
        include_date: Whether to show signature date
    
    Returns:
        Markup: Safe HTML/SVG for signature
    """
    if signature_date is None:
        signature_date = datetime.now().strftime('%d %B %Y')
    
    date_html = f'<div style="text-align: center; font-size: 9px; color: #7f8c8d; margin-top: 2px;">Signed: {signature_date}</div>' if include_date else ''
    
    # SVG path for cursive handwritten signature resembling "Makokha" in cursive style
    signature_html = f"""
    <div style="display: inline-block; margin: 20px 0;">
        <svg width="280" height="80" viewBox="0 0 280 80" xmlns="http://www.w3.org/2000/svg" style="background: transparent;">
            <!-- Cursive signature path (resembling handwritten "Makokha") -->
            <g stroke="#1e3a8a" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <!-- M -->
                <path d="M 15,45 Q 15,20 25,25 L 30,45 Q 32,25 40,30 L 43,50" stroke-width="3"/>
                
                <!-- a -->
                <path d="M 50,38 Q 55,32 62,36 Q 68,40 64,48 Q 60,55 52,52 Q 48,50 50,45" stroke-width="2.5"/>
                <path d="M 64,36 L 66,52" stroke-width="2.5"/>
                
                <!-- k -->
                <path d="M 75,22 L 75,52" stroke-width="2.8"/>
                <path d="M 75,38 Q 82,32 88,38 M 75,42 Q 82,48 90,52" stroke-width="2.5"/>
                
                <!-- o -->
                <path d="M 95,36 Q 102,32 108,36 Q 114,42 108,48 Q 102,54 95,48 Q 90,42 95,36" stroke-width="2.5"/>
                
                <!-- k -->
                <path d="M 118,22 L 118,52" stroke-width="2.8"/>
                <path d="M 118,38 Q 125,32 131,38 M 118,42 Q 125,48 133,52" stroke-width="2.5"/>
                
                <!-- h -->
                <path d="M 142,20 L 142,52" stroke-width="2.8"/>
                <path d="M 142,36 Q 148,32 154,36 L 154,52" stroke-width="2.5"/>
                
                <!-- a -->
                <path d="M 162,38 Q 167,32 174,36 Q 180,40 176,48 Q 172,55 164,52 Q 160,50 162,45" stroke-width="2.5"/>
                <path d="M 176,36 L 178,52" stroke-width="2.5"/>
                
                <!-- Underline flourish -->
                <path d="M 10,58 Q 140,62 270,58" stroke-width="1.8" opacity="0.6"/>
            </g>
        </svg>
        <div style="text-align: center; font-size: 11px; color: #2c3e50; margin-top: 5px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">
            {signer_title}
        </div>
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
