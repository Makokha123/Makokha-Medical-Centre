# Resend Domain Configuration Guide

## ⚠️ IMPORTANT: Test Domain Limitations

By default, this application uses Resend's test domain: `onboarding@resend.dev`

**Limitation**: Resend's test domain can **ONLY** send emails to:
- Email addresses that are verified in your Resend dashboard
- Emails you've explicitly whitelisted for testing

This means that in production, emails will **silently fail** for any unverified recipients.

## Solution: Add Your Own Domain

To send emails to ANY valid email address, you must add and verify your own domain.

### Step 1: Choose Your Domain

You need a domain you own (e.g., `makokhamedical.com`, `yourcompany.com`).

### Step 2: Add Domain to Resend

1. Go to [Resend Domains](https://resend.com/domains)
2. Click **"Add Domain"**
3. Enter your domain name
4. Choose your region

### Step 3: Verify Domain with DNS Records

Resend will provide DNS records you need to add to your domain:

1. **SPF Record** (TXT record)
   - Prevents email spoofing
   - Example: `v=spf1 include:_spf.resend.com ~all`

2. **DKIM Record** (TXT record)
   - Authenticates your emails
   - Example: `resend._domainkey` → `p=MIGfMA0GCSqGSIb3...`

3. **DMARC Record** (TXT record) - Optional but recommended
   - Protects against email spoofing
   - Example: `v=DMARC1; p=none;`

**Where to add these records:**
- If using **Cloudflare**: DNS → Add Record
- If using **GoDaddy**: DNS Management → Add Record
- If using **Namecheap**: Domain List → Manage → Advanced DNS
- Other registrars: Look for "DNS Management" or "DNS Settings"

### Step 4: Wait for Verification

- DNS changes can take 5-60 minutes to propagate
- Resend will automatically verify your domain once DNS is updated
- Check verification status in Resend dashboard

### Step 5: Update Environment Variable

Once your domain is verified, update your `.env` file:

```env
# OLD (test domain - only sends to verified emails)
RESEND_FROM=Makokha Medical Centre <onboarding@resend.dev>

# NEW (your verified domain - sends to ANY email)
RESEND_FROM=Makokha Medical Centre <noreply@makokhamedical.com>
```

Replace `makokhamedical.com` with your actual verified domain.

### Step 6: Restart Application

```bash
# Restart your Flask application
# The new domain will be loaded from .env
```

## Email Address Formats

Once configured, you can use various email formats:

```env
RESEND_FROM=noreply@yourdomain.com
RESEND_FROM=Makokha Medical Centre <noreply@yourdomain.com>
RESEND_FROM=Contact <contact@yourdomain.com>
```

## Recommended Email Addresses

Choose one of these common patterns:

- `noreply@yourdomain.com` - For automated emails
- `notifications@yourdomain.com` - For system notifications
- `support@yourdomain.com` - If you want replies
- `info@yourdomain.com` - General information

## Troubleshooting

### Emails still not sending?

1. **Check DNS propagation**:
   ```bash
   nslookup -type=TXT yourdomain.com
   ```

2. **Verify in Resend dashboard**:
   - Go to [Resend Domains](https://resend.com/domains)
   - Ensure status shows "Verified" with green checkmark

3. **Check application logs**:
   - Look for warnings about "test domain" in Flask logs
   - Check `instance/email_audit.log` for send failures

4. **Test with Resend API**:
   - Go to Resend dashboard → API Keys
   - Use their testing tool to send a test email

### Common DNS Issues

**Issue**: DNS not propagating
- **Solution**: Wait longer (up to 24 hours in rare cases)
- **Check**: Use [DNS Checker](https://dnschecker.org/) to verify propagation

**Issue**: DKIM record too long
- **Solution**: Some DNS providers require splitting long TXT records
- **Check**: Resend documentation for your specific provider

**Issue**: Multiple TXT records at same subdomain
- **Solution**: Most providers allow multiple TXT records at `_domainkey`
- **Check**: Each record should be separate, not combined

## Production Checklist

Before going live, ensure:

- [ ] Domain added and verified in Resend dashboard
- [ ] SPF record added to DNS
- [ ] DKIM record added to DNS
- [ ] DMARC record added to DNS (recommended)
- [ ] `RESEND_FROM` updated in `.env` file
- [ ] Application restarted with new configuration
- [ ] Test email sent to external address (not your domain)
- [ ] Check email lands in inbox (not spam)

## Email Deliverability Tips

1. **Warm up your domain**: Start with low volume, gradually increase
2. **Monitor spam reports**: Check Resend analytics
3. **Add SPF, DKIM, DMARC**: All three improve deliverability
4. **Use real reply-to address**: Shows legitimacy
5. **Include unsubscribe link**: Required for bulk emails
6. **Avoid spam trigger words**: FREE, URGENT, ACT NOW, etc.

## Cost Considerations

**Resend Pricing** (as of 2024):
- **Free Tier**: 3,000 emails/month
- **Pro Tier**: $20/month for 50,000 emails
- Additional emails: $1 per 1,000 emails

For a medical center:
- Estimate daily emails (OTPs, notifications, reports)
- Free tier usually sufficient for small/medium practices

## Alternative: Whitelist Emails for Testing

If you don't have a domain yet, you can whitelist specific emails:

1. Go to [Resend Dashboard](https://resend.com/overview)
2. Navigate to Settings → Verified Emails
3. Add email addresses you want to test with
4. Click verification link in email
5. Now those emails will receive test emails

**Note**: This is only for development/testing, not production.

## Support

- **Resend Documentation**: https://resend.com/docs
- **Resend Support**: support@resend.com
- **DNS Help**: Contact your domain registrar

## Current Configuration

To check your current email configuration:

```bash
# View current RESEND_FROM setting
grep RESEND_FROM .env

# Check Flask startup logs for warning about test domain
# Look for: "⚠ IMPORTANT: Using Resend test domain"
```

If you see the test domain warning, follow this guide to configure production domain.
