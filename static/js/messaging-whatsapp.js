/**
 * WhatsApp-Like Messaging System - Complete JavaScript Implementation
 * Handles real-time messaging, calls, file uploads, and WebRTC signaling
 */

// Initialize Socket.IO connection
let socket = null;
let currentConversation = null;
let currentUserId = null;
let localStream = null;
let peerConnection = null;
let incomingCall = null;

// Initialize messaging system
class WhatsAppMessaging {
    constructor() {
        this.conversations = new Map();
        this.messages = new Map();
        this.currentConversationId = null;
        this.callActive = false;
        this.messageQueue = [];
        this.init();
    }

    /**
     * Initialize the messaging system
     */
    async init() {
        try {
            // Get current user ID
            currentUserId = await this.getCurrentUserId();

            // Initialize Socket.IO
            this.initializeSocket();

            // Load conversations
            await this.loadConversations();

            // Setup event listeners
            this.setupEventListeners();

            console.log('? Messaging system initialized');
        } catch (error) {
            console.error('Failed to initialize messaging:', error);
        }
    }

    /**
     * Get current user ID from backend
     */
    getCurrentUserId() {
        return fetch('/api/current_user')
            .then(res => res.json())
            .then(data => data.user_id);
    }

    /**
     * Initialize Socket.IO connection
     */
    initializeSocket() {
        socket = io({
            path: '/socket.io',
            transports: ['polling', 'websocket'],
            withCredentials: true
        });

        // Connection events
        socket.on('connect', () => {
            console.log('? Socket.IO connected:', socket.id);
            this.updateOnlineStatus(true);
        });

        socket.on('disconnect', () => {
            console.warn('? Socket.IO disconnected');
            this.updateOnlineStatus(false);
        });

        // Message events
        socket.on('new_message', (data) => this.handleNewMessage(data));
        socket.on('message_read', (data) => this.handleMessageRead(data));
        socket.on('message_delivered', (data) => this.handleMessageDelivered(data));
        socket.on('typing', (data) => this.handleTyping(data));
        socket.on('message_edited', (data) => this.handleMessageEdited(data));
        socket.on('message_deleted', (data) => this.handleMessageDeleted(data));

        // Call events
        socket.on('incoming_call', (data) => this.handleIncomingCall(data));
        socket.on('call_rejected', (data) => this.handleCallRejected(data));
        socket.on('call_ended', (data) => this.handleCallEnded(data));

        // WebRTC events
        socket.on('webrtc_offer', (data) => this.handleWebRtcOffer(data));
        socket.on('webrtc_answer', (data) => this.handleWebRtcAnswer(data));
        socket.on('webrtc_ice', (data) => this.handleWebRtcIce(data));

        // User status events
        socket.on('user_online', (data) => this.handleUserOnline(data));
        socket.on('user_offline', (data) => this.handleUserOffline(data));
    }

    /**
     * Load conversations from server
     */
    async loadConversations() {
        try {
            const response = await fetch('/api/conversations');
            const data = await response.json();

            const list = document.getElementById('conversationsList');
            list.innerHTML = '';

            if (!data.conversations || data.conversations.length === 0) {
                list.innerHTML = `
                    <div class="empty-state">
                        <i class="bi bi-chat-dots"></i>
                        <p>No conversations yet</p>
                        <button class="btn btn-sm btn-primary" id="startConversationBtn">Start a chat</button>
                    </div>
                `;
                return;
            }

            data.conversations.forEach(conv => {
                const item = this.createConversationItem(conv);
                list.appendChild(item);
            });
        } catch (error) {
            console.error('Failed to load conversations:', error);
        }
    }

    /**
     * Create conversation list item element
     */
    createConversationItem(conv) {
        const div = document.createElement('div');
        div.className = 'conversation-item';
        div.dataset.conversationId = conv.id;
        div.dataset.userId = conv.user_id;

        const avatar = document.createElement('div');
        avatar.className = `conversation-avatar ${conv.is_online ? 'online' : ''}`;
        avatar.textContent = conv.initials;

        const info = document.createElement('div');
        info.className = 'conversation-info';

        const header = document.createElement('div');
        header.className = 'conversation-header';
        header.innerHTML = `
            <span class="conversation-name">${this.escapeHtml(conv.name)}</span>
            <span class="conversation-time">${conv.last_message_time}</span>
        `;

        const message = document.createElement('div');
        message.className = `conversation-message ${conv.unread ? 'unread' : ''}`;
        message.textContent = conv.last_message;

        info.appendChild(header);
        info.appendChild(message);

        if (conv.unread_count > 0) {
            const badge = document.createElement('div');
            badge.className = 'unread-badge';
            badge.textContent = conv.unread_count;
            div.appendChild(badge);
        }

        div.appendChild(avatar);
        div.appendChild(info);

        div.addEventListener('click', () => this.openConversation(conv.id, conv.user_id, conv.name));

        return div;
    }

    /**
     * Open a conversation
     */
    async openConversation(conversationId, userId, username) {
        this.currentConversationId = conversationId;
        currentConversation = { id: conversationId, user_id: userId, name: username };

        // Update UI
        document.getElementById('chatEmpty').style.display = 'none';
        document.getElementById('messagesContainer').style.display = 'flex';
        document.getElementById('messageInputArea').style.display = 'flex';
        document.getElementById('chatHeader').style.display = 'flex';

        // Update header
        document.getElementById('chatHeaderName').textContent = username;
        document.getElementById('voiceCallBtn').disabled = false;
        document.getElementById('videoCallBtn').disabled = false;

        // Load messages
        await this.loadMessages(conversationId);

        // Mark as read
        await this.markConversationAsRead(conversationId);

        // Join Socket.IO room
        socket.emit('join_conversation', { conversation_id: conversationId });

        // Reload conversations to update UI
        await this.loadConversations();
    }

    /**
     * Load messages for a conversation
     */
    async loadMessages(conversationId, page = 1) {
        try {
            const response = await fetch(`/api/conversation/${conversationId}/messages?page=${page}`);
            const data = await response.json();

            const messagesList = document.getElementById('messagesList');
            messagesList.innerHTML = '';

            if (!data.messages || data.messages.length === 0) {
                messagesList.innerHTML = '<div class="text-center text-muted">No messages yet</div>';
                return;
            }

            data.messages.forEach(msg => {
                const msgElement = this.createMessageElement(msg);
                messagesList.appendChild(msgElement);
            });

            // Scroll to bottom
            const container = document.getElementById('messagesContainer');
            container.scrollTop = container.scrollHeight;
        } catch (error) {
            console.error('Failed to load messages:', error);
        }
    }

    /**
     * Create message element
     */
    createMessageElement(msg) {
        const group = document.createElement('div');
        group.className = `message-group ${msg.is_sender ? 'sent' : 'received'}`;
        group.dataset.messageId = msg.id;

        if (!msg.is_sender) {
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = msg.sender_name.charAt(0).toUpperCase();
            group.appendChild(avatar);
        }

        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${msg.is_sender ? 'sent' : 'received'} ${msg.edited ? 'edited' : ''}`;

        // Content
        const content = document.createElement('div');
        content.className = 'message-content';

        if (msg.reply_to) {
            const reply = document.createElement('div');
            reply.className = 'message-reply';
            reply.innerHTML = `
                <div class="reply-author">${msg.reply_to.sender_name}</div>
                <div class="reply-text">${this.escapeHtml(msg.reply_to.content).substring(0, 100)}</div>
            `;
            content.appendChild(reply);
        }

        if (msg.attachments && msg.attachments.length > 0) {
            msg.attachments.forEach(att => {
                const attEl = this.createAttachmentElement(att);
                content.appendChild(attEl);
            });
        }

        if (msg.content) {
            const text = document.createElement('div');
            text.className = 'message-text';
            text.innerHTML = this.formatMessageText(msg.content);
            content.appendChild(text);
        }

        bubble.appendChild(content);

        // Meta
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        meta.innerHTML = `
            <span class="message-time">${new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            ${msg.is_sender ? `
                <span class="message-status">
                    <span class="status-check ${msg.is_read ? 'read' : msg.is_delivered ? 'delivered' : ''}">
                        ${msg.is_read ? '??' : msg.is_delivered ? '??' : '?'}
                    </span>
                </span>
            ` : ''}
        `;
        bubble.appendChild(meta);

        // Reactions
        if (msg.reactions && msg.reactions.length > 0) {
            const reactions = document.createElement('div');
            reactions.className = 'message-reactions';
            msg.reactions.forEach(reaction => {
                const react = document.createElement('span');
                react.className = 'reaction-item';
                react.textContent = reaction.emoji;
                reactions.appendChild(react);
            });
            bubble.appendChild(reactions);
        }

        group.appendChild(bubble);

        // Context menu
        bubble.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.showMessageContextMenu(e, msg);
        });

        return group;
    }

    /**
     * Create attachment element
     */
    createAttachmentElement(att) {
        const div = document.createElement('div');
        div.className = 'message-attachment';

        if (att.file_type === 'image') {
            const img = document.createElement('img');
            img.src = att.file_url;
            img.className = 'message-image';
            img.style.cursor = 'pointer';
            img.addEventListener('click', () => this.showImageLightbox(att.file_url));
            div.appendChild(img);
        } else if (att.file_type === 'video') {
            const video = document.createElement('video');
            video.src = att.file_url;
            video.className = 'message-video';
            video.controls = true;
            div.appendChild(video);
        } else if (att.file_type === 'audio') {
            const audio = document.createElement('audio');
            audio.src = att.file_url;
            audio.className = 'message-audio';
            audio.controls = true;
            div.appendChild(audio);
        } else {
            const file = document.createElement('a');
            file.href = att.file_url;
            file.target = '_blank';
            file.className = 'message-file';
            file.innerHTML = `
                <div class="file-icon">
                    <i class="bi bi-file-earmark"></i>
                </div>
                <div class="file-info">
                    <div class="file-name">${att.file_name}</div>
                    <div class="file-size">${this.formatFileSize(att.file_size)}</div>
                </div>
            `;
            div.appendChild(file);
        }

        return div;
    }

    /**
     * Send message
     */
    async sendMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();

        if (!content || !this.currentConversationId) return;

        try {
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    conversation_id: this.currentConversationId,
                    content: content
                })
            });

            const data = await response.json();

            if (data.success) {
                input.value = '';
                input.style.height = 'auto';

                // Emit via Socket.IO for real-time
                socket.emit('send_message', {
                    conversation_id: this.currentConversationId,
                    content: content
                });

                // Reload messages
                await this.loadMessages(this.currentConversationId);
            }
        } catch (error) {
            console.error('Failed to send message:', error);
        }
    }

    /**
     * Handle new message from Socket.IO
     */
    handleNewMessage(data) {
        if (data.conversation_id === this.currentConversationId) {
            this.loadMessages(this.currentConversationId);
            this.markMessageAsDelivered(data.message_id);
        }
        this.loadConversations();
    }

    /**
     * Handle message read status
     */
    handleMessageRead(data) {
        if (data.conversation_id === this.currentConversationId) {
            const msgEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
            if (msgEl) {
                const checkmark = msgEl.querySelector('.status-check');
                if (checkmark) checkmark.classList.add('read');
            }
        }
    }

    /**
     * Handle message delivered status
     */
    handleMessageDelivered(data) {
        if (data.conversation_id === this.currentConversationId) {
            const msgEl = document.querySelector(`[data-message-id="${data.message_id}"]`);
            if (msgEl) {
                const checkmark = msgEl.querySelector('.status-check');
                if (checkmark) checkmark.classList.add('delivered');
            }
        }
    }

    /**
     * Mark conversation as read
     */
    async markConversationAsRead(conversationId) {
        try {
            await fetch(`/api/conversation/${conversationId}/read`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
        } catch (error) {
            console.error('Failed to mark as read:', error);
        }
    }

    /**
     * Mark message as delivered
     */
    async markMessageAsDelivered(messageId) {
        try {
            await fetch(`/api/message/${messageId}/delivered`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
        } catch (error) {
            console.error('Failed to mark as delivered:', error);
        }
    }

    /**
     * Initiate voice call
     */
    async startVoiceCall() {
        try {
            localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            await this.initializePeerConnection('voice');

            socket.emit('initiate_call', {
                conversation_id: this.currentConversationId,
                type: 'voice'
            });

            this.showCallModal(true);
        } catch (error) {
            console.error('Failed to start voice call:', error);
            alert('Microphone access denied');
        }
    }

    /**
     * Initiate video call
     */
    async startVideoCall() {
        try {
            localStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: { width: { ideal: 1280 }, height: { ideal: 720 } }
            });
            await this.initializePeerConnection('video');

            socket.emit('initiate_call', {
                conversation_id: this.currentConversationId,
                type: 'video'
            });

            this.showCallModal(false);
        } catch (error) {
            console.error('Failed to start video call:', error);
            alert('Camera/Microphone access denied');
        }
    }

    /**
     * Initialize WebRTC peer connection
     */
    async initializePeerConnection(callType) {
        const config = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };

        peerConnection = new RTCPeerConnection(config);

        // Add local stream tracks
        if (localStream) {
            localStream.getTracks().forEach(track => {
                peerConnection.addTrack(track, localStream);
            });
        }

        // Handle ICE candidates
        peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                socket.emit('webrtc_ice', {
                    conversation_id: this.currentConversationId,
                    candidate: event.candidate
                });
            }
        };

        // Handle remote stream
        peerConnection.ontrack = (event) => {
            const remoteVideo = document.getElementById('remoteVideo');
            if (remoteVideo && event.streams[0]) {
                remoteVideo.srcObject = event.streams[0];
            }
        };

        // Handle connection state changes
        peerConnection.onconnectionstatechange = () => {
            console.log('Connection state:', peerConnection.connectionState);
            if (peerConnection.connectionState === 'disconnected' || 
                peerConnection.connectionState === 'failed' ||
                peerConnection.connectionState === 'closed') {
                this.endCall();
            }
        };

        // Create and send offer
        try {
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);

            socket.emit('webrtc_offer', {
                conversation_id: this.currentConversationId,
                sdp: offer
            });
        } catch (error) {
            console.error('Failed to create offer:', error);
        }
    }

    /**
     * Handle incoming call
     */
    async handleIncomingCall(data) {
        incomingCall = data;
        this.showIncomingCallModal(data);
    }

    /**
     * Accept incoming call
     */
    async acceptCall() {
        try {
            const callType = incomingCall.type;
            const constraints = {
                audio: true,
                video: callType === 'video'
            };

            localStream = await navigator.mediaDevices.getUserMedia(constraints);
            await this.initializePeerConnection(callType);

            document.getElementById('incomingCallModal').style.display = 'none';
            this.showCallModal(callType === 'voice');

            socket.emit('accept_call', {
                conversation_id: this.currentConversationId
            });
        } catch (error) {
            console.error('Failed to accept call:', error);
        }
    }

    /**
     * Reject incoming call
     */
    rejectCall() {
        socket.emit('reject_call', {
            conversation_id: this.currentConversationId
        });
        document.getElementById('incomingCallModal').style.display = 'none';
    }

    /**
     * Handle WebRTC offer
     */
    async handleWebRtcOffer(data) {
        try {
            if (!peerConnection) {
                await this.initializePeerConnection('video');
            }

            const offer = new RTCSessionDescription(data.sdp);
            await peerConnection.setRemoteDescription(offer);

            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);

            socket.emit('webrtc_answer', {
                conversation_id: this.currentConversationId,
                sdp: answer
            });
        } catch (error) {
            console.error('Failed to handle offer:', error);
        }
    }

    /**
     * Handle WebRTC answer
     */
    async handleWebRtcAnswer(data) {
        try {
            const answer = new RTCSessionDescription(data.sdp);
            await peerConnection.setRemoteDescription(answer);
        } catch (error) {
            console.error('Failed to handle answer:', error);
        }
    }

    /**
     * Handle WebRTC ICE candidate
     */
    async handleWebRtcIce(data) {
        try {
            if (data.candidate && peerConnection) {
                await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        } catch (error) {
            console.error('Failed to handle ICE:', error);
        }
    }

    /**
     * End call
     */
    endCall() {
        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
        }

        if (peerConnection) {
            peerConnection.close();
            peerConnection = null;
        }

        document.getElementById('callModal').style.display = 'none';
        document.getElementById('localVideo').srcObject = null;
        document.getElementById('remoteVideo').srcObject = null;

        socket.emit('end_call', {
            conversation_id: this.currentConversationId
        });

        this.callActive = false;
    }

    /**
     * Handle incoming call rejection
     */
    handleCallRejected(data) {
        alert('Call was rejected');
        this.endCall();
    }

    /**
     * Handle call ended
     */
    handleCallEnded(data) {
        this.endCall();
    }

    /**
     * Handle typing indicator
     */
    handleTyping(data) {
        const indicator = document.getElementById('typingIndicator');
        if (data.conversation_id === this.currentConversationId) {
            document.getElementById('typingText').textContent = `${data.username} is typing...`;
            indicator.style.display = 'flex';

            clearTimeout(this.typingTimeout);
            this.typingTimeout = setTimeout(() => {
                indicator.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * Handle online status
     */
    handleUserOnline(data) {
        this.updateUserOnlineStatus(data.user_id, true);
    }

    /**
     * Handle offline status
     */
    handleUserOffline(data) {
        this.updateUserOnlineStatus(data.user_id, false);
    }

    /**
     * Update user online status in UI
     */
    updateUserOnlineStatus(userId, isOnline) {
        // Update conversation items
        const items = document.querySelectorAll(`[data-user-id="${userId}"] .conversation-avatar`);
        items.forEach(item => {
            if (isOnline) {
                item.classList.add('online');
            } else {
                item.classList.remove('online');
            }
        });

        // Update status indicator if this is current conversation
        if (currentConversation && currentConversation.user_id === userId) {
            const statusDot = document.querySelector('.status-dot');
            const statusText = document.getElementById('statusText');

            if (statusDot) {
                if (isOnline) {
                    statusDot.classList.add('online');
                    statusText.textContent = 'online';
                } else {
                    statusDot.classList.remove('online');
                    statusText.textContent = 'offline';
                }
            }
        }
    }

    /**
     * Show call modal
     */
    showCallModal(isVoice = false) {
        const modal = document.getElementById('callModal');
        const localVideo = document.getElementById('localVideo');
        const localWrapper = document.querySelector('.local-video-wrapper');

        if (isVoice) {
            localWrapper.style.display = 'none';
        } else {
            localWrapper.style.display = 'block';
            if (localStream) {
                localVideo.srcObject = localStream;
            }
        }

        modal.style.display = 'flex';
        this.callActive = true;

        // Update call duration
        let duration = 0;
        this.callDurationInterval = setInterval(() => {
            duration++;
            const mins = Math.floor(duration / 60);
            const secs = duration % 60;
            document.getElementById('callDuration').textContent = 
                `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }, 1000);
    }

    /**
     * Show incoming call modal
     */
    showIncomingCallModal(data) {
        const modal = document.getElementById('incomingCallModal');
        const name = document.getElementById('callerName');
        const avatar = document.getElementById('callerAvatar');
        const label = document.getElementById('callTypeLabel');

        name.textContent = data.caller_name;
        avatar.src = data.caller_avatar || '/static/images/default-avatar.png';
        label.textContent = data.type === 'video' ? 'Incoming video call...' : 'Incoming voice call...';

        modal.style.display = 'flex';
    }

    /**
     * Show image lightbox
     */
    showImageLightbox(imageUrl) {
        const lightbox = document.createElement('div');
        lightbox.style.cssText = `
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.95);
            z-index: 3000;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        `;

        const img = document.createElement('img');
        img.src = imageUrl;
        img.style.cssText = 'max-width: 90%; max-height: 90%; object-fit: contain;';

        lightbox.appendChild(img);
        document.body.appendChild(lightbox);

        lightbox.addEventListener('click', () => {
            lightbox.remove();
        });
    }

    /**
     * Show message context menu
     */
    showMessageContextMenu(event, msg) {
        // Implementation for message context menu
        // Options: Reply, Edit, Delete, React, Forward
        console.log('Context menu for message:', msg);
    }

    /**
     * Format message text with links, emojis, etc.
     */
    formatMessageText(text) {
        // Escape HTML
        text = this.escapeHtml(text);

        // Replace line breaks
        text = text.replace(/\n/g, '<br>');

        // Add emoji support
        // text = this.addEmojiSupport(text);

        // Add link detection
        text = text.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');

        return text;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Send button
        document.getElementById('sendBtn').addEventListener('click', () => this.sendMessage());

        // Enter to send
        document.getElementById('messageInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        const textarea = document.getElementById('messageInput');
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
        });

        // Calls
        document.getElementById('voiceCallBtn').addEventListener('click', () => this.startVoiceCall());
        document.getElementById('videoCallBtn').addEventListener('click', () => this.startVideoCall());

        // End call
        document.getElementById('endCallBtn').addEventListener('click', () => this.endCall());

        // Accept/Reject call
        document.getElementById('acceptCallBtn').addEventListener('click', () => this.acceptCall());
        document.getElementById('rejectCallBtn').addEventListener('click', () => this.rejectCall());

        // Attach menu
        document.getElementById('attachBtn').addEventListener('click', () => {
            const menu = document.getElementById('attachMenu');
            menu.style.display = menu.style.display === 'none' ? 'grid' : 'none';
        });

        // File uploads
        document.getElementById('uploadPhotoBtn').addEventListener('click', () => {
            document.getElementById('photoInput').click();
        });

        document.getElementById('uploadVideoBtn').addEventListener('click', () => {
            document.getElementById('videoInput').click();
        });

        document.getElementById('uploadAudioBtn').addEventListener('click', () => {
            document.getElementById('audioInput').click();
        });

        document.getElementById('uploadDocumentBtn').addEventListener('click', () => {
            document.getElementById('documentInput').click();
        });

        // File input handlers
        document.getElementById('photoInput').addEventListener('change', (e) => this.handleFileUpload(e, 'image'));
        document.getElementById('videoInput').addEventListener('change', (e) => this.handleFileUpload(e, 'video'));
        document.getElementById('audioInput').addEventListener('change', (e) => this.handleFileUpload(e, 'audio'));
        document.getElementById('documentInput').addEventListener('change', (e) => this.handleFileUpload(e, 'document'));

        // New chat
        document.getElementById('newChatBtn').addEventListener('click', () => {
            const modal = new bootstrap.Modal(document.getElementById('newChatModal'));
            modal.show();
        });

        // Search conversations
        document.getElementById('conversationSearch').addEventListener('input', (e) => {
            this.searchConversations(e.target.value);
        });
    }

    /**
     * Handle file upload
     */
    async handleFileUpload(event, fileType) {
        const file = event.target.files[0];
        if (!file || !this.currentConversationId) return;

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('conversation_id', this.currentConversationId);

            const response = await fetch('/api/upload_attachment', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            const data = await response.json();

            if (data.success) {
                // Send message with attachment
                await this.sendAttachmentMessage(data.attachment_id, fileType);
            }
        } catch (error) {
            console.error('Failed to upload file:', error);
        }

        // Clear input
        event.target.value = '';
    }

    /**
     * Send message with attachment
     */
    async sendAttachmentMessage(attachmentId, fileType) {
        try {
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    conversation_id: this.currentConversationId,
                    attachment_id: attachmentId,
                    message_type: fileType
                })
            });

            const data = await response.json();

            if (data.success) {
                await this.loadMessages(this.currentConversationId);
                await this.loadConversations();
            }
        } catch (error) {
            console.error('Failed to send attachment message:', error);
        }
    }

    /**
     * Search conversations
     */
    async searchConversations(query) {
        try {
            const response = await fetch(`/api/conversations?search=${encodeURIComponent(query)}`);
            const data = await response.json();

            const list = document.getElementById('conversationsList');
            list.innerHTML = '';

            if (!data.conversations || data.conversations.length === 0) {
                list.innerHTML = '<div class="empty-state"><p>No results found</p></div>';
                return;
            }

            data.conversations.forEach(conv => {
                const item = this.createConversationItem(conv);
                list.appendChild(item);
            });
        } catch (error) {
            console.error('Failed to search conversations:', error);
        }
    }

    /**
     * Update online status
     */
    updateOnlineStatus(isOnline) {
        socket.emit('update_status', { is_online: isOnline });
    }

    /**
     * Handle message edited
     */
    handleMessageEdited(data) {
        if (data.conversation_id === this.currentConversationId) {
            this.loadMessages(this.currentConversationId);
        }
    }

    /**
     * Handle message deleted
     */
    handleMessageDeleted(data) {
        if (data.conversation_id === this.currentConversationId) {
            this.loadMessages(this.currentConversationId);
        }
    }

    /**
     * Handle typing indicator
     */
    handleTyping(data) {
        if (data.conversation_id === this.currentConversationId) {
            const typingEl = document.getElementById('typingIndicator');
            const typingText = document.getElementById('typingText');
            if (typingEl && typingText) {
                typingEl.style.display = 'flex';
                typingText.textContent = `${data.username} is typing...`;
                
                // Auto hide after 3 seconds
                clearTimeout(this.typingTimeout);
                this.typingTimeout = setTimeout(() => {
                    typingEl.style.display = 'none';
                }, 3000);
            }
        }
    }

    /**
     * Send typing indicator
     */
    notifyTyping() {
        if (this.currentConversationId) {
            socket.emit('typing', {
                conversation_id: this.currentConversationId
            });
        }
    }

    /**
     * Search messages
     */
    async searchMessages(query) {
        try {
            if (!query || query.length < 2) {
                return;
            }

            const response = await fetch(`/api/search/messages?q=${encodeURIComponent(query)}&conversation_id=${this.currentConversationId}`);
            const data = await response.json();

            if (data.success && data.results.length > 0) {
                const resultsContainer = document.createElement('div');
                resultsContainer.className = 'search-results';

                data.results.forEach(result => {
                    const item = document.createElement('div');
                    item.className = 'search-result-item';
                    item.innerHTML = `
                        <div class="search-result-preview">${this.escapeHtml(result.snippet)}</div>
                        <div class="search-result-meta">From ${result.sender_username} • ${new Date(result.created_at).toLocaleString()}</div>
                    `;
                    item.addEventListener('click', () => {
                        this.scrollToMessage(result.id);
                    });
                    resultsContainer.appendChild(item);
                });

                // Insert or update results container
                const existingResults = document.querySelector('.search-results');
                if (existingResults) existingResults.remove();
                document.body.appendChild(resultsContainer);
            }
        } catch (error) {
            console.error('Search failed:', error);
        }
    }

    /**
     * Scroll to a specific message
     */
    scrollToMessage(messageId) {
        const msgEl = document.querySelector(`[data-message-id="${messageId}"]`);
        if (msgEl) {
            msgEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            msgEl.classList.add('highlight');
            setTimeout(() => msgEl.classList.remove('highlight'), 2000);
        }
    }

    /**
     * Get all contacts
     */
    async loadContacts() {
        try {
            const response = await fetch('/api/contacts');
            const data = await response.json();

            if (data.success) {
                const contactsList = document.getElementById('usersList');
                if (contactsList) {
                    contactsList.innerHTML = '';
                    
                    if (data.contacts.length === 0) {
                        contactsList.innerHTML = '<p class="text-center text-muted">No contacts yet</p>';
                        return;
                    }

                    data.contacts.forEach(contact => {
                        const item = document.createElement('div');
                        item.className = 'contact-item';
                        item.innerHTML = `
                            <div class="contact-avatar">${contact.username.charAt(0).toUpperCase()}</div>
                            <div class="contact-info">
                                <div class="contact-name">${contact.username}</div>
                                <div class="contact-role">${contact.role}</div>
                            </div>
                            <button class="contact-action" title="Chat">
                                <i class="bi bi-chat-dots"></i>
                            </button>
                        `;
                        
                        item.querySelector('.contact-action').addEventListener('click', (e) => {
                            e.stopPropagation();
                            this.openConversation(contact.id, contact.username);
                        });

                        contactsList.appendChild(item);
                    });
                }
            }
        } catch (error) {
            console.error('Failed to load contacts:', error);
        }
    }

    /**
     * Utility: Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Utility: Format file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    /**
     * Utility: Get CSRF token
     */
    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || '';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.messaging = new WhatsAppMessaging();

    // Setup search
    const conversationSearch = document.getElementById('conversationSearch');
    if (conversationSearch) {
        conversationSearch.addEventListener('input', (e) => {
            window.messaging.searchMessages(e.target.value);
        });
    }

    // Setup message input for typing indicators
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', () => {
            window.messaging.notifyTyping();
        });
    }

