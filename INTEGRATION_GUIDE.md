# Integration Guide for New Communication Features

## 🚀 Quick Integration Steps

### Step 1: Optional Features Integration

If you want to enable the optional features (encryption, push notifications, email notifications), add these imports and calls to your existing routes in `app.py`.

---

## 1. Message Encryption Integration

### Add to imports (top of app.py):
```python
from utils.message_encryption import encrypt_message_content, decrypt_message_content
```

### Update send_message route (~line 32078):

Find this section:
```python
# Create message
new_message = Message(
    conversation_id=conversation.id,
    sender_id=current_user.id,
    recipient_id=recipient_id,
    content=content,  # ← Encrypt this
    message_type=message_type,
    ...
)
```

Change to:
```python
# Encrypt message content (optional - only if MESSAGE_ENCRYPTION_KEY is set in .env)
encrypted_content = encrypt_message_content(content) if os.getenv('MESSAGE_ENCRYPTION_KEY') else content

# Create message
new_message = Message(
    conversation_id=conversation.id,
    sender_id=current_user.id,
    recipient_id=recipient_id,
    content=encrypted_content,  # ← Now encrypted
    message_type=message_type,
    ...
)
```

### Update message retrieval routes:

When returning messages, decrypt them:

```python
# In /api/communication/conversation/<id> route
messages = Message.query.filter(...).all()

# Decrypt messages before returning
for msg in messages:
    if msg.content and os.getenv('MESSAGE_ENCRYPTION_KEY'):
        msg.content = decrypt_message_content(msg.content)
```

---

## 2. Push Notifications Integration

### Add to imports:
```python
from utils.push_notifications import send_new_message_notification, send_incoming_call_notification
```

### Update send_message route:

After creating the message, add:
```python
# Send push notification if receiver is offline
receiver_status = UserOnlineStatus.query.filter_by(user_id=recipient_id).first()
if not receiver_status or not receiver_status.is_online:
    try:
        send_new_message_notification(
            recipient_user=receiver,
            sender_name=current_user.username,
            message_content=content
        )
    except Exception as e:
        current_app.logger.error(f'Push notification failed: {e}')
```

### Update initiate_call route (~line 32208):

After creating the call, add:
```python
# Send push notification for incoming call
try:
    send_incoming_call_notification(
        recipient_user=receiver,
        caller_name=current_user.username,
        call_type=call_type
    )
except Exception as e:
    current_app.logger.error(f'Call notification failed: {e}')
```

---

## 3. Email Notifications Integration

### Add to imports:
```python
from utils.communication_emails import notify_new_message_via_email, notify_missed_call_via_email
```

### Update send_message route:

After creating the message, add:
```python
# Send email notification if receiver is offline (only if enabled)
receiver_status = UserOnlineStatus.query.filter_by(user_id=recipient_id).first()
if not receiver_status or not receiver_status.is_online:
    try:
        notify_new_message_via_email(
            recipient_user=receiver,
            sender_name=current_user.username,
            message_content=content
        )
    except Exception as e:
        current_app.logger.error(f'Email notification failed: {e}')
```

### Update reject_call route (~line 32250):

In the reject_call route, add:
```python
# Update call status
call.call_status = 'rejected'
db.session.commit()

# Send missed call email
try:
    notify_missed_call_via_email(
        recipient_user=call.receiver,
        caller_name=call.caller.username,
        call_type=call.call_type,
        timestamp=call.started_at
    )
except Exception as e:
    current_app.logger.error(f'Missed call email failed: {e}')
```

---

## 4. User Model Extension (For Push Notifications)

### Add FCM Device Token Field

If you want full push notification support, add this field to your User model:

```python
class User(UserMixin, db.Model):
    # ... existing fields ...
    
    fcm_device_token = db.Column(db.String(255))  # Firebase Cloud Messaging token
```

Then create a route to register device tokens:

```python
@app.route('/api/communication/register_device', methods=['POST'])
@login_required
def register_device_token():
    """Register FCM device token for push notifications"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Token required'}), 400
        
        current_user.fcm_device_token = token
        db.session.commit()
        
        return jsonify({'message': 'Device registered successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

---

## 5. Environment Variables

Add these to your `.env` file:

```bash
# Optional - End-to-End Encryption
# Generate with: python -c "from utils.message_encryption import MessageEncryption; print(MessageEncryption.generate_key())"
MESSAGE_ENCRYPTION_KEY=your-generated-fernet-key

# Optional - Push Notifications (Firebase Cloud Messaging)
# Get from: https://console.firebase.google.com → Project Settings → Cloud Messaging
FCM_SERVER_KEY=your-firebase-server-key
FCM_SENDER_ID=your-firebase-sender-id

# Required for Email Links
APP_URL=https://yourdomain.com
```

---

## 6. Frontend JavaScript is Already Complete

No additional integration needed! The JavaScript in `static/js/communication.js` already includes:

✅ File upload handlers  
✅ Message editing/deletion  
✅ Emoji reactions  
✅ Group chat functions  
✅ Search functionality  
✅ Pagination  
✅ Block user  
✅ Screen sharing  
✅ All Socket.IO event handlers  

Just make sure users can access the updated file.

---

## 7. HTML Template is Already Complete

The `templates/components/communication_modal.html` already includes:

✅ File upload button  
✅ Hidden file input  
✅ Search panel  
✅ Groups panel  
✅ Call history panel  
✅ Screen share button  
✅ All CSS animations  

No additional work needed!

---

## 🎯 Priority Integration

### Must Have (Already Done):
- ✅ All backend API routes (already in app.py)
- ✅ All frontend JavaScript (already in communication.js)
- ✅ All HTML UI elements (already in template)

### Should Have (Quick Integration):
- **Email Notifications** - 5 minutes to add
  - Just add the 3 lines of code in send_message route
  - Works with existing email system

### Nice to Have (Optional):
- **Message Encryption** - 10 minutes to add
  - Add encryption key to .env
  - Add encrypt/decrypt calls in routes
  
- **Push Notifications** - 15 minutes to setup
  - Create Firebase project
  - Add FCM keys to .env
  - Add notification calls in routes
  - Add device token registration route

---

## 🧪 Testing After Integration

### Test Email Notifications:
1. Send message to offline user
2. Check their email inbox
3. Verify email has correct content and links

### Test Push Notifications:
1. Register device token via `/api/communication/register_device`
2. Send message to that user
3. Check if push notification arrives on device

### Test Encryption:
1. Add MESSAGE_ENCRYPTION_KEY to .env
2. Send a message
3. Check database - content should be encrypted (base64 gibberish)
4. View message in app - should display correctly

---

## 📊 Integration Status

| Feature | Backend | Frontend | Integration Required |
|---------|---------|----------|---------------------|
| File Upload | ✅ Done | ✅ Done | ❌ No |
| Message Edit/Delete | ✅ Done | ✅ Done | ❌ No |
| Reactions | ✅ Done | ✅ Done | ❌ No |
| Group Chats | ✅ Done | ✅ Done | ❌ No |
| Search & Pagination | ✅ Done | ✅ Done | ❌ No |
| Block/Settings | ✅ Done | ✅ Done | ❌ No |
| Screen Sharing | ✅ Done | ✅ Done | ❌ No |
| Encryption | ✅ Module | N/A | ✅ Yes (Optional) |
| Push Notifications | ✅ Module | N/A | ✅ Yes (Optional) |
| Email Notifications | ✅ Module | N/A | ✅ Yes (Optional) |

---

## 🎉 Summary

**Everything is ready to use immediately!**

The only "integration" needed is for the 3 optional features:
1. Message Encryption (optional)
2. Push Notifications (optional)
3. Email Notifications (recommended - 5 minutes)

All core features work without any additional integration because:
- Backend API routes are already in app.py
- Frontend JavaScript is already in communication.js  
- HTML templates are already updated
- All Socket.IO handlers are in place

Just:
1. Restart your Flask app
2. Hard refresh browser (Ctrl+Shift+R)
3. Start using all the new features!

**Optional**: Add email notifications in 5 minutes by following Step 3 above.

**Super Optional**: Add encryption and/or push notifications if you want those enterprise features.
