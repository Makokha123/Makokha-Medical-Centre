# Dynamic Rubber Stamp & Digital Signature System

## Overview
Your system now has **automatic, date-stamped rubber stamps and digital signatures** that can be added to ANY document, receipt, or report. The date updates automatically based on the current date.

## Features
✅ **System-generated** - No images needed, all code-based
✅ **Auto-updating date** - Always shows current date
✅ **Professional appearance** - Looks like real rubber stamp
✅ **Reusable** - Use on any page/document
✅ **Customizable** - Change colors, sizes, names
✅ **Print-ready** - Maintains quality when printed

---

## How to Use in Templates

### Method 1: Using Helper Functions (RECOMMENDED)

#### Add Rubber Stamp
```html
{{ generate_rubber_stamp() }}
```

**With custom options:**
```html
{{ generate_rubber_stamp(
    facility_name="Makokha Medical Centre",
    location="Nairobi • Kenya",
    current_date=None,  <!-- Will use today's date -->
    stamp_color="#c0392b",
    size=200
) }}
```

#### Add Digital Signature
```html
{{ generate_digital_signature() }}
```

**With custom options:**
```html
{{ generate_digital_signature(
    signer_name="Dr. J. Makokha",
    signer_title="Medical Director",
    signature_date=None,  <!-- Will use today's date -->
    include_date=True
) }}
```

### Method 2: Using Include Components

#### Add Rubber Stamp
```html
{% set current_date = now.strftime('%d %b %Y') %}
{% include 'admin/components/dynamic_stamp.html' %}
```

#### Add Digital Signature
```html
{% set signature_date = now.strftime('%d %B %Y') %}
{% set signer_name = "Dr. J. Makokha" %}
{% set signer_title = "Medical Director" %}
{% include 'admin/components/digital_signature.html' %}
```

---

## Examples

### Example 1: LPO/Invoice (Already Implemented)
```html
<div class="signature-section">
    <div class="signature-box">
        {{ generate_digital_signature() }}
    </div>
    
    <div class="stamp-box">
        {{ generate_rubber_stamp() }}
    </div>
</div>
```

### Example 2: Prescription
```html
<div style="margin-top: 40px;">
    {{ generate_digital_signature(
        signer_name="Dr. Jane Makokha",
        signer_title="Medical Officer"
    ) }}
</div>
```

### Example 3: Receipt
```html
<div style="text-align: right;">
    {{ generate_rubber_stamp(size=150) }}
</div>
```

### Example 4: Lab Report
```html
<div style="display: flex; justify-content: space-between;">
    <div>
        {{ generate_digital_signature(
            signer_name="Dr. Lab Technician",
            signer_title="Chief Lab Officer"
        ) }}
    </div>
    <div>
        {{ generate_rubber_stamp(size=180) }}
    </div>
</div>
```

---

## Customization Options

### Rubber Stamp Parameters:
- `facility_name`: Your facility name (default: "Makokha Medical Centre")
- `location`: Location text (default: "Nairobi • Kenya")
- `current_date`: Date to display (default: today's date)
- `stamp_color`: Color hex code (default: "#c0392b" - red)
- `size`: Size in pixels (default: 200)

### Digital Signature Parameters:
- `signer_name`: Name of person signing (default: "Dr. J. Makokha")
- `signer_title`: Title/position (default: "Medical Director")
- `signature_date`: Date of signature (default: today's date)
- `include_date`: Show date below signature (default: True)

---

## Date Formats

### Get Current Dates:
```html
<!-- Stamp format: "16 Jan 2026" -->
{{ get_current_stamp_date() }}

<!-- Signature format: "16 January 2026" -->
{{ get_current_signature_date() }}
```

---

## Where to Add Stamps/Signatures

### Suggested Documents:
1. ✅ **LPOs** (Local Purchase Orders) - DONE
2. **Invoices** - Add to invoice template
3. **Receipts** - Add to payment receipts
4. **Prescriptions** - Add doctor's signature
5. **Lab Reports** - Add lab officer signature
6. **Medical Certificates** - Add stamp + signature
7. **Discharge Summaries** - Add doctor's signature
8. **Insurance Claims** - Add stamp for authenticity
9. **Expense Reports** - Add for approval
10. **Payroll Slips** - Add authorized signature

---

## Implementation Guide

### To Add to Any Existing Template:

1. **Open the template file** (e.g., `templates/admin/invoice.html`)

2. **Find where signature/stamp should appear** (usually at bottom)

3. **Add this code:**
```html
<div style="margin-top: 50px; display: flex; justify-content: space-between;">
    <div style="width: 45%;">
        {{ generate_digital_signature() }}
    </div>
    <div style="width: 45%; text-align: right;">
        {{ generate_rubber_stamp() }}
    </div>
</div>
```

4. **Done!** The stamp and signature will appear with today's date automatically.

---

## Advanced Customization

### Change Stamp Color:
```html
<!-- Green stamp -->
{{ generate_rubber_stamp(stamp_color="#27ae60") }}

<!-- Blue stamp -->
{{ generate_rubber_stamp(stamp_color="#3498db") }}

<!-- Purple stamp -->
{{ generate_rubber_stamp(stamp_color="#8e44ad") }}
```

### Different Sizes:
```html
<!-- Small stamp -->
{{ generate_rubber_stamp(size=150) }}

<!-- Large stamp -->
{{ generate_rubber_stamp(size=250) }}
```

### Multiple Signatories:
```html
<div style="display: flex; gap: 40px;">
    {{ generate_digital_signature(
        signer_name="Dr. J. Makokha",
        signer_title="Medical Director"
    ) }}
    
    {{ generate_digital_signature(
        signer_name="Nurse M. Wanjiku",
        signer_title="Head Nurse"
    ) }}
</div>
```

---

## Benefits

### Why This is Better Than Images:
1. ✅ **Always up-to-date** - Date changes automatically
2. ✅ **No file management** - No need to upload/store images
3. ✅ **Consistent** - Same look across all documents
4. ✅ **Lightweight** - No image files to load
5. ✅ **Scalable** - Looks crisp at any size
6. ✅ **Customizable** - Easy to change colors/text
7. ✅ **Print-perfect** - High quality when printed
8. ✅ **Professional** - Legal-looking official stamp

---

## Troubleshooting

### If stamp doesn't appear:
1. Check that `utils/stamp_signature.py` exists
2. Ensure template has access to `generate_rubber_stamp()` function
3. Check for CSS conflicts

### If date is wrong:
The date uses server time. Ensure your server timezone is set to EAT (East Africa Time).

### To change default signer:
Edit in `app.py` route or pass directly in template:
```html
{{ generate_digital_signature(signer_name="Your Name") }}
```

---

## Legal Validity (Kenya Context)

### Digital Signatures in Kenya:
- ✅ **Legally recognized** under Kenya Information and Communications Act
- ✅ **Acceptable** for most business transactions
- ✅ **Valid** for LPOs, invoices, receipts
- ⚠️ **May need physical stamp** for government contracts
- ⚠️ **KRA may require additional authentication** for tax documents

### Best Practice:
- Use **digital stamps/signatures** for daily operations
- Keep **physical stamp** for legal/government documents
- Both together = maximum validity

---

## Next Steps

1. ✅ **LPOs now have stamps** - Already implemented
2. **Add to invoices** - Copy same code to invoice template
3. **Add to receipts** - Add to payment receipt template
4. **Add to prescriptions** - Add doctor's signature
5. **Test printing** - Verify quality on printed copies

---

## Support

If you need to customize further or add to more documents, the code is in:
- **Generator:** `utils/stamp_signature.py`
- **Components:** `templates/admin/components/`
- **LPO Example:** `templates/admin/lpo_pdf.html`

Copy the patterns from LPO to any other document!
