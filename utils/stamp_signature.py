"""
Digital Stamp and Signature Generator
Generates dynamic, date-stamped official stamps and loads hand-drawn signatures
"""
from datetime import datetime
from markupsafe import Markup
import os

def generate_rubber_stamp(facility_name="MAKOKHA MEDICAL CENTRE", 
                          email="makokhamedicalcentre2025@gmail.com",
                          phone1="0741 256 531",
                          phone2="0713 580 997",
                          current_date=None,
                          stamp_color="#2e3192",
                          size=200):
    """
    Generate SVG for a rectangular rubber stamp matching the provided image
    
    Args:
        facility_name: Name of the facility (default: MAKOKHA MEDICAL CENTRE)
        email: Email address
        phone1: First phone number
        phone2: Second phone number
        current_date: Date to display (default: today in format "21 DEC 2025")
        stamp_color: Color of stamp (default: blue #2e3192)
        size: Width in pixels (default: 200 for receipts)
    
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
                               include_date=True,
                               user_id=None):
    """
    Load hand-drawn signature from database or show placeholder
    
    This function is now a placeholder that tells templates to use the signature_pad component.
    The actual signature rendering happens client-side via JavaScript.
    
    Args:
        signer_name: Name of person signing (default: Makokha)
        signer_title: Title/position of signer  
        signature_date: Date of signature (default: today)
        include_date: Whether to show signature date
        user_id: User ID to load signature for (optional)
    
    Returns:
        Markup: HTML comment indicating signature pad should be used
    """
    if signature_date is None:
        signature_date = datetime.now().strftime('%d %B %Y')
    
    # Return a marker that indicates signature pad component should be included
    # The actual rendering is handled by the signature_pad.html template
    signature_html = f"""
    <!-- SIGNATURE_PAD: title="{signer_title}" date="{signature_date}" -->
    <div class="signature-container" data-signer-title="{signer_title}" data-signature-date="{signature_date}">
        <!-- Signature will be loaded here by signature_pad.html component -->
    </div>
    """
    
    return Markup(signature_html)


def get_current_stamp_date():
    """Get current date formatted for stamp"""
    return datetime.now().strftime('%d %b %Y')


def get_current_signature_date():
    """Get current date formatted for signature"""
    return datetime.now().strftime('%d %B %Y')
