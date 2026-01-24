import secrets

# Generate a strong, URL-safe secret
cron_secret = secrets.token_urlsafe(32)

print("\nGenerated CRON_SECRET:\n")
print(cron_secret)
print("\nSave this in Render Environment Variables as CRON_SECRET\n")
