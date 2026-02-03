/**
 * Real-time Communication System
 * Handles messaging, voice calls, and video calls
 */

class CommunicationSystem {
    constructor() {
        this.socket = null;
        this.currentUserId = null;
        this.currentUser = null;
        this.activeConversation = null;
        this.activeChatUserId = null;
        this.peerConnection = null;
        this.localStream = null;
        this.remoteStream = null;
        this.callType = null;
        this.callId = null;
        this.isMuted = false;
        this.isVideoEnabled = true;
        this.callDurationInterval = null;
        this.typingTimeout = null;
        this.eatTimezone = 'Africa/Nairobi'; // EAT timezone

        // Audio (ringtones) + WebRTC configuration
        this._audioContext = null;
        this._toneStopFn = null;
        this._iceServersCache = null;
        this._callRole = null; // 'caller' | 'callee'

        // Messaging UX state
        this._messageCache = new Map();
        this._replyToMessageId = null;
        this._isChatBlocked = false;
        this._emojiPickerEl = null;
        this._messageActionsEl = null;
        this._chatSettingsEl = null;
        
        this.init();
    }

    init() {
        // Initialize Socket.IO connection
        this.socket = io();
        
        // Get current user info from the page
        this.currentUserId = this.getCurrentUserId();
        
        // Setup Socket.IO event listeners
        this.setupSocketListeners();
        
        // Setup UI event listeners
        this.setupUIListeners();
        
        // Setup drag functionality
        this.setupDragFunctionality();
        
        // Load users list
        this.loadUsers();
        
        // Request notification permission
        this.requestNotificationPermission();

        // Prepare audio context on first user gesture (autoplay policies)
        this.armAudioOnFirstGesture();
    }

    armAudioOnFirstGesture() {
        const enable = () => {
            try {
                if (!this._audioContext) {
                    const AudioCtx = window.AudioContext || window.webkitAudioContext;
                    if (AudioCtx) this._audioContext = new AudioCtx();
                }
                if (this._audioContext && this._audioContext.state === 'suspended') {
                    this._audioContext.resume().catch(() => {});
                }
            } catch (_) {
                // no-op
            }
            document.removeEventListener('click', enable, true);
            document.removeEventListener('touchstart', enable, true);
            document.removeEventListener('keydown', enable, true);
        };

        document.addEventListener('click', enable, true);
        document.addEventListener('touchstart', enable, true);
        document.addEventListener('keydown', enable, true);
    }

    getCurrentUserId() {
        // Try to get user ID from data attribute or meta tag
        const userIdElement = document.querySelector('[data-user-id]');
        if (userIdElement) {
            return parseInt(userIdElement.getAttribute('data-user-id'));
        }
        
        // Fallback: try to get from meta tag
        const metaUserId = document.querySelector('meta[name="user-id"]');
        if (metaUserId) {
            return parseInt(metaUserId.content);
        }
        
        return null;
    }

    setupSocketListeners() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('Connected to Socket.IO server');
            if (this.currentUserId) {
                this.socket.emit('user_connected', { user_id: this.currentUserId });
            }
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from Socket.IO server');
        });

        // Message events
        this.socket.on('new_message', (data) => {
            this.handleNewMessage(data);
        });

        this.socket.on('message_delivered', (data) => {
            this.handleMessageDelivered(data);
        });

        this.socket.on('message_read', (data) => {
            this.handleMessageRead(data);
        });

        this.socket.on('typing_status', (data) => {
            this.handleTypingStatus(data);
        });

        // User status events
        this.socket.on('user_status_update', (data) => {
            this.handleUserStatusUpdate(data);
        });

        // Call events
        this.socket.on('incoming_call', (data) => {
            this.handleIncomingCall(data);
        });

        this.socket.on('call_accepted', (data) => {
            this.handleCallAccepted(data);
        });

        this.socket.on('call_rejected', (data) => {
            this.handleCallRejected(data);
        });

        this.socket.on('call_ended', (data) => {
            this.handleCallEnded(data);
        });

        // WebRTC signaling events
        this.socket.on('webrtc_offer', (data) => {
            this.handleWebRTCOffer(data);
        });

        this.socket.on('webrtc_answer', (data) => {
            this.handleWebRTCAnswer(data);
        });

        this.socket.on('webrtc_ice_candidate', (data) => {
            this.handleWebRTCIceCandidate(data);
        });
    }

    setupUIListeners() {
        // Float icon click
        const floatIcon = document.getElementById('communication-float-icon');
        if (floatIcon) {
            floatIcon.addEventListener('click', () => this.toggleCommunicationModal());
        }

        // Close and minimize buttons
        const closeBtn = document.getElementById('close-chat');
        const minimizeBtn = document.getElementById('minimize-chat');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeCommunicationModal());
        }
        
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', () => this.minimizeCommunicationModal());
        }

        // Search users
        const searchInput = document.getElementById('search-users');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.searchUsers(e.target.value));
        }

        // Send message
        const sendBtn = document.getElementById('send-message-btn');
        const messageInput = document.getElementById('message-input');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        if (messageInput) {
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });
            
            messageInput.addEventListener('input', () => {
                this.handleTyping();
            });
        }

        // Call buttons
        const voiceCallBtn = document.getElementById('voice-call-btn');
        const videoCallBtn = document.getElementById('video-call-btn');
        
        if (voiceCallBtn) {
            voiceCallBtn.addEventListener('click', () => this.initiateCall('voice'));
        }
        
        if (videoCallBtn) {
            videoCallBtn.addEventListener('click', () => this.initiateCall('video'));
        }

        // Call control buttons
        const acceptCallBtn = document.getElementById('accept-call-btn');
        const rejectCallBtn = document.getElementById('reject-call-btn');
        const endCallBtn = document.getElementById('end-call-btn');
        const muteBtn = document.getElementById('mute-btn');
        const toggleVideoBtn = document.getElementById('toggle-video-btn');
        
        if (acceptCallBtn) {
            acceptCallBtn.addEventListener('click', () => this.acceptCall());
        }
        
        if (rejectCallBtn) {
            rejectCallBtn.addEventListener('click', () => this.rejectCall());
        }
        
        if (endCallBtn) {
            endCallBtn.addEventListener('click', () => this.endCall());
        }

        const cancelCallBtn = document.getElementById('cancel-call-btn');
        if (cancelCallBtn) {
            cancelCallBtn.addEventListener('click', () => this.endCall());
        }
        
        if (muteBtn) {
            muteBtn.addEventListener('click', () => this.toggleMute());
        }
        
        if (toggleVideoBtn) {
            toggleVideoBtn.addEventListener('click', () => this.toggleVideo());
        }

        const emojiBtn = document.getElementById('emoji-btn');
        if (emojiBtn) {
            emojiBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleEmojiPicker(emojiBtn);
            });
        }

        const replyCancelBtn = document.getElementById('reply-cancel-btn');
        if (replyCancelBtn) {
            replyCancelBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearReply();
            });
        }

        const chatSearchBtn = document.getElementById('chat-search-btn');
        const chatSearchClose = document.getElementById('chat-search-close');
        if (chatSearchBtn) {
            chatSearchBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleChatSearch(true);
            });
        }
        if (chatSearchClose) {
            chatSearchClose.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleChatSearch(false);
            });
        }

        const chatSearchInput = document.getElementById('chat-search-input');
        if (chatSearchInput) {
            let searchTimer = null;
            chatSearchInput.addEventListener('input', () => {
                if (!this.activeChatUserId) return;
                if (searchTimer) clearTimeout(searchTimer);
                searchTimer = setTimeout(() => this.searchMessages(chatSearchInput.value), 300);
            });
        }

        const chatSettingsBtn = document.getElementById('chat-settings-btn');
        if (chatSettingsBtn) {
            chatSettingsBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleChatSettings(chatSettingsBtn);
            });
        }

        // Mobile responsive handlers
        this.setupMobileHandlers();
    }

    setupMobileHandlers() {
        // Add back button functionality for mobile
        const backToUsersBtn = document.getElementById('back-to-users');
        if (backToUsersBtn) {
            backToUsersBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.showUsersList();
            });
        }

        const chatHeader = document.querySelector('.chat-header');
        if (chatHeader && window.innerWidth <= 767) {
            chatHeader.style.cursor = 'pointer';
            chatHeader.addEventListener('click', (e) => {
                if (e.target.closest('.chat-actions')) return;
                if (e.target.closest('#back-to-users')) return;
                this.showUsersList();
            });
        }

        // Handle window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });

        // Handle orientation change
        window.addEventListener('orientationchange', () => {
            setTimeout(() => this.handleResize(), 100);
        });
    }

    handleResize() {
        const isMobile = window.innerWidth <= 767;
        const chatHeader = document.querySelector('.chat-header');
        
        if (isMobile && chatHeader) {
            chatHeader.style.cursor = 'pointer';
        } else if (chatHeader) {
            chatHeader.style.cursor = 'default';
        }
    }

    showUsersList() {
        const usersSidebar = document.getElementById('users-sidebar');
        const chatArea = document.getElementById('chat-area');
        
        if (usersSidebar && chatArea) {
            usersSidebar.classList.remove('hidden');
            chatArea.style.display = 'none';
        }
    }

    hideUsersList() {
        const usersSidebar = document.getElementById('users-sidebar');
        const chatArea = document.getElementById('chat-area');
        
        if (window.innerWidth <= 767) {
            if (usersSidebar) {
                usersSidebar.classList.add('hidden');
            }
            if (chatArea) {
                chatArea.style.display = 'flex';
            }
        }
    }

    toggleCommunicationModal() {
        const modal = document.getElementById('communication-modal');
        if (modal) {
            if (modal.style.display === 'none') {
                modal.style.display = 'flex';
            } else {
                modal.style.display = 'none';
            }
        }
    }

    closeCommunicationModal() {
        const modal = document.getElementById('communication-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    minimizeCommunicationModal() {
        const modal = document.getElementById('communication-modal');
        if (modal) {
            modal.classList.toggle('minimized');
        }
    }

    async loadUsers() {
        try {
            const response = await fetch('/api/communication/users', {
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to load users');
            }
            
            const data = await response.json();
            this.displayUsers(data.users);
        } catch (error) {
            console.error('Error loading users:', error);
            this.showError('Failed to load users');
        }
    }

    displayUsers(users) {
        const usersList = document.getElementById('users-list');
        if (!usersList) return;
        
        usersList.innerHTML = '';
        
        if (users.length === 0) {
            usersList.innerHTML = '<div class="text-center text-muted py-4"><p>No users found</p></div>';
            return;
        }
        
        const sortedUsers = [...users].sort((a, b) => {
            const ap = a.is_pinned ? 1 : 0;
            const bp = b.is_pinned ? 1 : 0;
            if (ap !== bp) return bp - ap;
            const au = a.unread_count || 0;
            const bu = b.unread_count || 0;
            if (au !== bu) return bu - au;
            return String(a.username || '').localeCompare(String(b.username || ''));
        });

        sortedUsers.forEach(user => {
            const userItem = document.createElement('div');
            userItem.className = 'user-item';
            userItem.dataset.userId = user.id;
            
            const onlineBadge = user.is_online ? '<span class="online-badge"></span>' : '';
            
            const pinBadge = user.is_pinned ? '<span class="badge bg-warning text-dark ms-2">Pinned</span>' : '';
            const archivedBadge = user.is_archived ? '<span class="badge bg-secondary ms-2">Archived</span>' : '';
            const blockedBadge = (user.blocked_by_me || user.blocked_me) ? '<span class="badge bg-danger ms-2">Blocked</span>' : '';

            userItem.innerHTML = `
                <div class="user-avatar">
                    <i class="bi bi-person-circle"></i>
                    ${onlineBadge}
                </div>
                <div class="user-info">
                    <div class="user-name">${this.escapeHtml(user.username)}${pinBadge}${archivedBadge}${blockedBadge}</div>
                    <div class="user-role">${this.escapeHtml(user.role)}</div>
                </div>
                ${user.unread_count > 0 ? `<span class="unread-badge">${user.unread_count}</span>` : ''}
            `;
            
            userItem.addEventListener('click', () => this.openChat(user));
            usersList.appendChild(userItem);
        });
    }

    searchUsers(query) {
        const userItems = document.querySelectorAll('.user-item');
        const lowerQuery = query.toLowerCase();
        
        userItems.forEach(item => {
            const username = item.querySelector('.user-name').textContent.toLowerCase();
            const role = item.querySelector('.user-role').textContent.toLowerCase();
            
            if (username.includes(lowerQuery) || role.includes(lowerQuery)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }

    async openChat(user) {
        this.activeChatUserId = user.id;
        this.currentUser = user;
        this._isChatBlocked = !!(user.blocked_by_me || user.blocked_me);
        this.clearReply();
        
        // Hide users list on mobile
        this.hideUsersList();
        
        // Update UI
        const noChatSelected = document.querySelector('.no-chat-selected');
        const activeChat = document.getElementById('active-chat');
        
        if (noChatSelected) noChatSelected.style.display = 'none';
        if (activeChat) activeChat.style.display = 'flex';
        
        // Update chat header
        document.getElementById('chat-user-name').textContent = user.username;
        const statusElement = document.getElementById('chat-user-status');
        if (statusElement) {
            if (user.is_online) {
                statusElement.textContent = 'online';
                statusElement.className = 'text-success';
            } else if (user.last_seen) {
                statusElement.textContent = `last seen ${this.formatDateTimeEAT(user.last_seen)}`;
                statusElement.className = 'text-muted';
            } else {
                statusElement.textContent = 'offline';
                statusElement.className = 'text-muted';
            }
        }

        this.applyChatBlockedUI();
        
        // Mark user item as active
        document.querySelectorAll('.user-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`.user-item[data-user-id="${user.id}"]`)?.classList.add('active');
        
        // Load conversation
        await this.loadConversation(user.id);
        
        // Join conversation room
        this.socket.emit('join_conversation', {
            user_id: this.currentUserId,
            other_user_id: user.id
        });
    }

    async loadConversation(otherUserId) {
        try {
            const response = await fetch(`/api/communication/conversation/${otherUserId}`, {
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to load conversation');
            }
            
            const data = await response.json();
            this.activeConversation = data.conversation;
            this.displayMessages(data.messages);
            
            // Mark messages as read
            this.markMessagesAsRead(otherUserId);
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    }

    displayMessages(messages) {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        messagesContainer.innerHTML = '';
        
        if (messages.length === 0) {
            messagesContainer.innerHTML = '<div class="text-center text-muted py-4"><p class="small">No messages yet. Start the conversation!</p></div>';
            return;
        }
        
        messages.forEach(message => {
            this.appendMessage(message, false);
        });
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    appendMessage(message, scrollToBottom = true) {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;

        if (message && message.message_id) {
            this._messageCache.set(message.message_id, message);
        }
        
        const isSent = message.sender_id === this.currentUserId;
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isSent ? 'sent' : 'received'}`;
        messageDiv.dataset.messageId = message.message_id;
        
        // Format time in EAT timezone
        const time = this.formatTimeEAT(message.created_at);
        
        // Generate tick marks for sent messages
        let tickMarks = '';
        if (isSent) {
            if (message.is_read) {
                // Two blue ticks for read
                tickMarks = '<span class="message-ticks read"><i class="bi bi-check-all"></i></span>';
            } else if (message.is_delivered) {
                // Two grey ticks for delivered
                tickMarks = '<span class="message-ticks delivered"><i class="bi bi-check-all"></i></span>';
            } else {
                // One grey tick for sent
                tickMarks = '<span class="message-ticks sent"><i class="bi bi-check"></i></span>';
            }
        }
        
        const deletedText = '<em class="text-muted">This message was deleted</em>';
        const repliedTo = message.replied_to ? `
            <div class="message-reply-preview">
                <div class="reply-snippet">${this.escapeHtml(message.replied_to.content || '')}</div>
            </div>
        ` : '';

        const reactionsHtml = (message.reactions && message.reactions.length) ? `
            <div class="message-reactions">
                ${message.reactions.map(r => `<span class="reaction-chip">${this.escapeHtml(r.emoji)} ${r.count}</span>`).join('')}
            </div>
        ` : '';

        const editedLabel = message.is_edited ? '<span class="message-edited">edited</span>' : '';
        const starLabel = message.is_starred ? '<i class="bi bi-star-fill message-star" title="Starred"></i>' : '';

        messageDiv.innerHTML = `
            <div class="message-bubble">
                ${repliedTo}
                <div class="message-content">${message.is_deleted ? deletedText : this.escapeHtml(message.content)}</div>
                ${reactionsHtml}
                <div class="message-time">
                    ${editedLabel}
                    ${starLabel}
                    ${time}
                    ${tickMarks}
                </div>
            </div>
        `;

        this.attachMessageInteractionHandlers(messageDiv);
        
        messagesContainer.appendChild(messageDiv);
        
        if (scrollToBottom) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    async sendMessage() {
        const messageInput = document.getElementById('message-input');
        if (!messageInput) return;
        
        const content = messageInput.value.trim();
        if (!content || !this.activeChatUserId) return;
        if (this._isChatBlocked) {
            this.showError('You cannot message this user (blocked).');
            return;
        }
        
        try {
            const response = await fetch('/api/communication/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    receiver_id: this.activeChatUserId,
                    content: content,
                    reply_to_message_id: this._replyToMessageId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to send message');
            }
            
            const data = await response.json();
            
            // Clear input
            messageInput.value = '';

            // Clear reply state
            this.clearReply();

            // Append immediately for sender
            if (data && data.message) {
                this.appendMessage(data.message);
            }
            
            // Emit socket event for real-time delivery
            this.socket.emit('send_message', {
                message: data.message,
                receiver_id: this.activeChatUserId
            });
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.showError('Failed to send message');
        }
    }

    handleNewMessage(data) {
        const message = data.message;
        
        // Emit message received confirmation
        this.socket.emit('message_received', {
            message_id: message.message_id,
            sender_id: message.sender_id
        });
        
        // If message is from current conversation, append it
        if (message.sender_id === this.activeChatUserId) {
            this.appendMessage(message);
            
            // Mark as read immediately
            this.markMessagesAsRead(this.activeChatUserId);
        } else {
            // Update unread count
            this.updateUnreadCount(message.sender_id);
            
            // Show notification
            this.showNotification(message);
        }
    }

    handleMessageDelivered(data) {
        // Update tick marks for delivered message
        const messageDiv = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageDiv) {
            const ticksElement = messageDiv.querySelector('.message-ticks');
            if (ticksElement) {
                ticksElement.className = 'message-ticks delivered';
                ticksElement.innerHTML = '<i class="bi bi-check-all"></i>';
            }
        }
    }

    handleMessageRead(data) {
        // Update tick marks for read message
        const messageDiv = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageDiv) {
            const ticksElement = messageDiv.querySelector('.message-ticks');
            if (ticksElement) {
                ticksElement.className = 'message-ticks read';
                ticksElement.innerHTML = '<i class="bi bi-check-all"></i>';
            }
        }
    }

    handleTyping() {
        if (!this.activeChatUserId) return;
        
        // Emit typing event
        this.socket.emit('typing', {
            receiver_id: this.activeChatUserId,
            is_typing: true
        });
        
        // Clear existing timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
        
        // Stop typing after 2 seconds of inactivity
        this.typingTimeout = setTimeout(() => {
            this.socket.emit('typing', {
                receiver_id: this.activeChatUserId,
                is_typing: false
            });
        }, 2000);
    }

    handleTypingStatus(data) {
        if (data.user_id !== this.activeChatUserId) return;
        
        const typingIndicator = document.getElementById('typing-indicator');
        if (!typingIndicator) return;
        
        if (data.is_typing) {
            typingIndicator.style.display = 'flex';
        } else {
            typingIndicator.style.display = 'none';
        }
    }

    async markMessagesAsRead(senderId) {
        try {
            await fetch('/api/communication/mark_read', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    sender_id: senderId
                })
            });
        } catch (error) {
            console.error('Error marking messages as read:', error);
        }
    }

    handleUserStatusUpdate(data) {
        // Update user status in the list
        const userItem = document.querySelector(`.user-item[data-user-id="${data.user_id}"]`);
        if (userItem) {
            const avatar = userItem.querySelector('.user-avatar');
            const existingBadge = avatar.querySelector('.online-badge');
            
            if (data.is_online) {
                if (!existingBadge) {
                    avatar.innerHTML += '<span class="online-badge"></span>';
                }
            } else {
                if (existingBadge) {
                    existingBadge.remove();
                }
            }
        }
        
        // Update chat header if this is the active user
        if (this.activeChatUserId === data.user_id) {
            const statusElement = document.getElementById('chat-user-status');
            if (statusElement) {
                if (data.is_online) {
                    statusElement.textContent = 'online';
                    statusElement.className = 'text-success';
                } else if (data.last_seen) {
                    statusElement.textContent = `last seen ${this.formatDateTimeEAT(data.last_seen)}`;
                    statusElement.className = 'text-muted';
                } else {
                    statusElement.textContent = 'offline';
                    statusElement.className = 'text-muted';
                }
            }
        }
    }

    applyChatBlockedUI() {
        const messageInput = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-message-btn');
        const voiceBtn = document.getElementById('voice-call-btn');
        const videoBtn = document.getElementById('video-call-btn');

        if (messageInput) messageInput.disabled = this._isChatBlocked;
        if (sendBtn) sendBtn.disabled = this._isChatBlocked;
        if (voiceBtn) voiceBtn.disabled = this._isChatBlocked;
        if (videoBtn) videoBtn.disabled = this._isChatBlocked;

        if (messageInput) {
            messageInput.placeholder = this._isChatBlocked ? 'Messaging disabled (blocked)' : 'Type a message...';
        }
    }

    attachMessageInteractionHandlers(messageDiv) {
        const messageId = messageDiv.dataset.messageId;
        if (!messageId) return;

        // Desktop: right-click
        messageDiv.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.openMessageActions(messageId, e.clientX, e.clientY);
        });

        // Desktop: double click
        messageDiv.addEventListener('dblclick', (e) => {
            this.openMessageActions(messageId, e.clientX, e.clientY);
        });

        // Mobile/tablet: long press
        let pressTimer = null;
        messageDiv.addEventListener('touchstart', (e) => {
            if (!e.touches || !e.touches[0]) return;
            const t = e.touches[0];
            pressTimer = setTimeout(() => {
                this.openMessageActions(messageId, t.clientX, t.clientY);
            }, 500);
        }, { passive: true });
        messageDiv.addEventListener('touchend', () => {
            if (pressTimer) clearTimeout(pressTimer);
        });
        messageDiv.addEventListener('touchmove', () => {
            if (pressTimer) clearTimeout(pressTimer);
        });
    }

    openMessageActions(messageId, x, y) {
        const message = this._messageCache.get(messageId);
        if (!message) return;
        if (message.is_deleted) return;

        if (!this._messageActionsEl) {
            const el = document.createElement('div');
            el.className = 'message-actions-popover';
            el.id = 'message-actions-popover';
            el.style.position = 'fixed';
            el.style.zIndex = '10001';
            el.style.display = 'none';
            document.body.appendChild(el);
            this._messageActionsEl = el;

            document.addEventListener('click', (e) => {
                if (this._messageActionsEl && this._messageActionsEl.style.display === 'block') {
                    if (!this._messageActionsEl.contains(e.target)) {
                        this._messageActionsEl.style.display = 'none';
                    }
                }
            });
        }

        const isSent = message.sender_id === this.currentUserId;
        const buttons = [];

        buttons.push({ label: 'Reply', icon: 'bi-reply', action: () => this.setReplyTo(message) });
        buttons.push({ label: message.is_starred ? 'Unstar' : 'Star', icon: message.is_starred ? 'bi-star-fill' : 'bi-star', action: () => this.toggleStar(messageId) });

        if (isSent) {
            buttons.push({ label: 'Edit', icon: 'bi-pencil', action: () => this.editMessage(messageId) });
            buttons.push({ label: 'Delete', icon: 'bi-trash', action: () => this.deleteMessage(messageId) });
        }

        const quickReactions = ['👍', '❤️', '😂', '😮', '😢', '🙏'];

        this._messageActionsEl.innerHTML = `
            <div class="quick-reactions">
                ${quickReactions.map(e => `<button type="button" class="quick-reaction-btn" data-emoji="${this.escapeHtml(e)}">${this.escapeHtml(e)}</button>`).join('')}
            </div>
            <div>
                ${buttons.map((b, idx) => `
                    <button type="button" class="btn" data-action-idx="${idx}">
                        <i class="bi ${b.icon}"></i>${this.escapeHtml(b.label)}
                    </button>
                `).join('')}
            </div>
        `;

        // Bind emoji buttons
        this._messageActionsEl.querySelectorAll('.quick-reaction-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const emoji = e.currentTarget.getAttribute('data-emoji');
                this.reactToMessage(messageId, emoji);
                this._messageActionsEl.style.display = 'none';
            });
        });

        // Bind action buttons
        this._messageActionsEl.querySelectorAll('button[data-action-idx]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.getAttribute('data-action-idx'));
                const b = buttons[idx];
                if (b && b.action) b.action();
                this._messageActionsEl.style.display = 'none';
            });
        });

        const margin = 8;
        const w = 240;
        const h = 220;
        const left = Math.max(margin, Math.min(x, window.innerWidth - w - margin));
        const top = Math.max(margin, Math.min(y, window.innerHeight - h - margin));
        this._messageActionsEl.style.left = `${left}px`;
        this._messageActionsEl.style.top = `${top}px`;
        this._messageActionsEl.style.display = 'block';
    }

    setReplyTo(message) {
        this._replyToMessageId = message.message_id;
        const preview = document.getElementById('reply-preview');
        const text = document.getElementById('reply-preview-text');
        if (preview && text) {
            text.textContent = (message.content || '').slice(0, 160);
            preview.style.display = 'flex';
        }
    }

    clearReply() {
        this._replyToMessageId = null;
        const preview = document.getElementById('reply-preview');
        if (preview) preview.style.display = 'none';
    }

    async editMessage(messageId) {
        const msg = this._messageCache.get(messageId);
        if (!msg) return;
        const next = prompt('Edit message:', msg.content || '');
        if (next === null) return;

        try {
            const response = await fetch(`/api/communication/message/${messageId}/edit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ content: next })
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to edit message');
            }

            msg.content = data.message.content;
            msg.is_edited = true;
            this._messageCache.set(messageId, msg);
            this.updateMessageElement(messageId);
        } catch (e) {
            console.error('Edit message failed:', e);
            this.showError('Failed to edit message');
        }
    }

    async deleteMessage(messageId) {
        if (!confirm('Delete this message for everyone?')) return;
        try {
            const response = await fetch(`/api/communication/message/${messageId}/delete`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to delete message');
            }
            const msg = this._messageCache.get(messageId);
            if (msg) {
                msg.is_deleted = true;
                msg.content = '';
                this._messageCache.set(messageId, msg);
                this.updateMessageElement(messageId);
            }
        } catch (e) {
            console.error('Delete message failed:', e);
            this.showError('Failed to delete message');
        }
    }

    async reactToMessage(messageId, emoji) {
        try {
            const response = await fetch(`/api/communication/message/${messageId}/react`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ emoji })
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to react');
            }

            // Optimistic local update: bump count for emoji (single-user view)
            const msg = this._messageCache.get(messageId);
            if (msg) {
                msg.my_reaction = data.my_reaction;
                // Force refresh by reloading conversation for accurate counts
                await this.loadConversation(this.activeChatUserId);
            }
        } catch (e) {
            console.error('React failed:', e);
        }
    }

    async toggleStar(messageId) {
        try {
            const response = await fetch(`/api/communication/message/${messageId}/star`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to star');
            }

            const msg = this._messageCache.get(messageId);
            if (msg) {
                msg.is_starred = !!data.is_starred;
                this._messageCache.set(messageId, msg);
                this.updateMessageElement(messageId);
            }
        } catch (e) {
            console.error('Star failed:', e);
        }
    }

    updateMessageElement(messageId) {
        const el = document.querySelector(`[data-message-id="${messageId}"]`);
        const msg = this._messageCache.get(messageId);
        if (!el || !msg) return;

        // Re-render using the same logic as appendMessage
        const isSent = msg.sender_id === this.currentUserId;
        el.className = `message ${isSent ? 'sent' : 'received'}`;

        const time = this.formatTimeEAT(msg.created_at);
        let tickMarks = '';
        if (isSent) {
            if (msg.is_read) tickMarks = '<span class="message-ticks read"><i class="bi bi-check-all"></i></span>';
            else if (msg.is_delivered) tickMarks = '<span class="message-ticks delivered"><i class="bi bi-check-all"></i></span>';
            else tickMarks = '<span class="message-ticks sent"><i class="bi bi-check"></i></span>';
        }

        const deletedText = '<em class="text-muted">This message was deleted</em>';
        const repliedTo = msg.replied_to ? `
            <div class="message-reply-preview">
                <div class="reply-snippet">${this.escapeHtml(msg.replied_to.content || '')}</div>
            </div>
        ` : '';

        const reactionsHtml = (msg.reactions && msg.reactions.length) ? `
            <div class="message-reactions">
                ${msg.reactions.map(r => `<span class="reaction-chip">${this.escapeHtml(r.emoji)} ${r.count}</span>`).join('')}
            </div>
        ` : '';

        const editedLabel = msg.is_edited ? '<span class="message-edited">edited</span>' : '';
        const starLabel = msg.is_starred ? '<i class="bi bi-star-fill message-star" title="Starred"></i>' : '';

        el.innerHTML = `
            <div class="message-bubble">
                ${repliedTo}
                <div class="message-content">${msg.is_deleted ? deletedText : this.escapeHtml(msg.content)}</div>
                ${reactionsHtml}
                <div class="message-time">
                    ${editedLabel}
                    ${starLabel}
                    ${time}
                    ${tickMarks}
                </div>
            </div>
        `;

        this.attachMessageInteractionHandlers(el);
    }

    toggleEmojiPicker(anchorEl) {
        if (!this._emojiPickerEl) {
            const el = document.createElement('div');
            el.id = 'emoji-picker';
            el.style.position = 'fixed';
            el.style.zIndex = '10001';
            el.style.background = '#fff';
            el.style.border = '1px solid rgba(0,0,0,0.12)';
            el.style.borderRadius = '12px';
            el.style.boxShadow = '0 8px 24px rgba(0,0,0,0.18)';
            el.style.padding = '10px';
            el.style.display = 'none';
            el.style.maxWidth = '260px';
            document.body.appendChild(el);
            this._emojiPickerEl = el;

            document.addEventListener('click', (e) => {
                if (this._emojiPickerEl && this._emojiPickerEl.style.display === 'block') {
                    if (!this._emojiPickerEl.contains(e.target) && e.target !== anchorEl) {
                        this._emojiPickerEl.style.display = 'none';
                    }
                }
            });
        }

        if (this._emojiPickerEl.style.display === 'block') {
            this._emojiPickerEl.style.display = 'none';
            return;
        }

        const emojis = [
            // Smileys & Emotion
            '😀','😃','😄','😁','😆','😅','🤣','😂','🙂','🙃','😉','😊','😇','🥰','😍','🤩','😘','😗','😚','😙',
            '😋','😛','😜','🤪','😝','🤑','🤗','🤭','🤫','🤔','🤐','🤨','😐','😑','😶','😏','😒','🙄','😬','🤥',
            '😌','😔','😪','🤤','😴','😷','🤒','🤕','🤢','🤮','🤧','🥵','🥶','🥴','😵','🤯','🤠','🥳','😎','🤓',
            '🧐','😕','😟','🙁','☹️','😮','😯','😲','😳','🥺','😦','😧','😨','😰','😥','😢','😭','😱','😖','😣',
            '😞','😓','😩','😫','🥱','😤','😡','😠','🤬','😈','👿','💀','☠️','💩','🤡','👹','👺','👻','👽','👾',
            '🤖','😺','😸','😹','😻','😼','😽','🙀','😿','😾',
            
            // Hearts & Love
            '❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','❣️','💕','💞','💓','💗','💖','💘','💝','💟',
            
            // Hand Gestures
            '👋','🤚','🖐️','✋','🖖','👌','🤌','🤏','✌️','🤞','🤟','🤘','🤙','👈','👉','👆','🖕','👇','☝️','👍',
            '👎','✊','👊','🤛','🤜','👏','🙌','👐','🤲','🤝','🙏','✍️','💅','🤳',
            
            // Body & People
            '💪','🦾','🦿','🦵','🦶','👂','🦻','👃','🧠','🦷','🦴','👀','👁️','👅','👄','💋',
            
            // Nature & Animals
            '🐶','🐱','🐭','🐹','🐰','🦊','🐻','🐼','🐨','🐯','🦁','🐮','🐷','🐸','🐵','🙈','🙉','🙊','🐔','🐧',
            '🐦','🐤','🐣','🐥','🦆','🦅','🦉','🦇','🐺','🐗','🐴','🦄','🐝','🐛','🦋','🐌','🐞','🐜','🦟','🦗',
            
            // Food & Drink
            '🍏','🍎','🍐','🍊','🍋','🍌','🍉','🍇','🍓','🫐','🍈','🍒','🍑','🥭','🍍','🥥','🥝','🍅','🍆','🥑',
            '🥦','🥬','🥒','🌶️','🫑','🌽','🥕','🫒','🧄','🧅','🥔','🍠','🥐','🥯','🍞','🥖','🥨','🧀','🥚','🍳',
            '🧈','🥞','🧇','🥓','🥩','🍗','🍖','🦴','🌭','🍔','🍟','🍕','🫓','🥪','🥙','🧆','🌮','🌯','🫔','🥗',
            '🍿','🧈','🧂','🥫','🍱','🍘','🍙','🍚','🍛','🍜','🍝','🍠','🍢','🍣','🍤','🍥','🥮','🍡','🥟','🥠',
            '🥡','🦀','🦞','🦐','🦑','🦪','🍦','🍧','🍨','🍩','🍪','🎂','🍰','🧁','🥧','🍫','🍬','🍭','🍮','🍯',
            '🍼','🥛','☕','🫖','🍵','🍶','🍾','🍷','🍸','🍹','🍺','🍻','🥂','🥃','🥤','🧋','🧃','🧉','🧊',
            
            // Activities & Sports
            '⚽','🏀','🏈','⚾','🥎','🎾','🏐','🏉','🥏','🎱','🪀','🏓','🏸','🏒','🏑','🥍','🏏','🥅','⛳','🪁',
            '🏹','🎣','🤿','🥊','🥋','🎽','🛹','🛼','🛷','⛸️','🥌','🎿','⛷️','🏂','🪂','🏋️','🤼','🤸','🤺','⛹️',
            '🤾','🏌️','🏇','🧘','🏊','🤽','🚣','🧗','🚴','🚵','🎪','🎭','🎨','🎬','🎤','🎧','🎼','🎹','🥁','🎷',
            '🎺','🎸','🪕','🎻','🎲','♟️','🎯','🎳','🎮','🎰','🧩',
            
            // Travel & Places
            '🚗','🚕','🚙','🚌','🚎','🏎️','🚓','🚑','🚒','🚐','🛻','🚚','🚛','🚜','🦯','🦽','🦼','🛴','🚲','🛵',
            '🏍️','🛺','🚨','🚔','🚍','🚘','🚖','🚡','🚠','🚟','🚃','🚋','🚞','🚝','🚄','🚅','🚈','🚂','🚆','🚇',
            '🚊','🚉','✈️','🛫','🛬','🛩️','💺','🛰️','🚁','🛸','🚀','🛶','⛵','🚤','🛥️','🛳️','⛴️','🚢','⚓','⛽',
            '🚧','🚦','🚥','🚏','🗺️','🗿','🗽','🗼','🏰','🏯','🏟️','🎡','🎢','🎠','⛲','⛱️','🏖️','🏝️','🏜️','🌋',
            '⛰️','🏔️','🗻','🏕️','⛺','🏠','🏡','🏘️','🏚️','🏗️','🏭','🏢','🏬','🏣','🏤','🏥','🏦','🏨','🏪','🏫',
            
            // Objects
            '⌚','📱','📲','💻','⌨️','🖥️','🖨️','🖱️','🖲️','🕹️','🗜️','💾','💿','📀','📼','📷','📸','📹','🎥','📽️',
            '🎞️','📞','☎️','📟','📠','📺','📻','🎙️','🎚️','🎛️','🧭','⏱️','⏲️','⏰','🕰️','⌛','⏳','📡','🔋','🔌',
            '💡','🔦','🕯️','🪔','🧯','🛢️','💸','💵','💴','💶','💷','💰','💳','💎','⚖️','🪜','🧰','🪛','🔧','🔨',
            '⚒️','🛠️','⛏️','🪚','🔩','⚙️','🪤','🧱','⛓️','🧲','🔫','💣','🧨','🪓','🔪','🗡️','⚔️','🛡️','🚬','⚰️',
            '⚱️','🏺','🔮','📿','🧿','💈','⚗️','🔭','🔬','🕳️','🩹','🩺','💊','💉','🩸','🧬','🦠','🧫','🧪','🌡️',
            '🧹','🧺','🧻','🚽','🚰','🚿','🛁','🛀','🧼','🪒','🧽','🧴','🛎️','🔑','🗝️','🚪','🪑','🛋️','🛏️','🛌',
            '🧸','🖼️','🛍️','🛒','🎁','🎈','🎏','🎀','🎊','🎉','🎎','🏮','🎐','🧧','✉️','📩','📨','📧','💌','📥',
            '📤','📦','🏷️','📪','📫','📬','📭','📮','📯','📜','📃','📄','📑','🧾','📊','📈','📉','🗒️','🗓️','📆',
            '📅','🗑️','📇','🗃️','🗳️','🗄️','📋','📁','📂','🗂️','🗞️','📰','📓','📔','📒','📕','📗','📘','📙','📚',
            
            // Symbols & Flags
            '❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','❣️','💕','💞','💓','💗','💖','💘','💝','💟','☮️',
            '✝️','☪️','🕉️','☸️','✡️','🔯','🕎','☯️','☦️','🛐','⛎','♈','♉','♊','♋','♌','♍','♎','♏','♐','♑',
            '♒','♓','🆔','⚛️','🉑','☢️','☣️','📴','📳','🈶','🈚','🈸','🈺','🈷️','✴️','🆚','💮','🉐','㊙️','㊗️',
            '🈴','🈵','🈹','🈲','🅰️','🅱️','🆎','🆑','🅾️','🆘','❌','⭕','🛑','⛔','📛','🚫','💯','💢','♨️','🚷',
            '🚯','🚳','🚱','🔞','📵','🚭','❗','❕','❓','❔','‼️','⁉️','🔅','🔆','〽️','⚠️','🚸','🔱','⚜️','🔰',
            '♻️','✅','🈯','💹','❇️','✳️','❎','🌐','💠','Ⓜ️','🌀','💤','🏧','🚾','♿','🅿️','🈳','🈂️','🛂','🛃',
            '🛄','🛅','🚹','🚺','🚼','🚻','🚮','🎦','📶','🈁','🔣','ℹ️','🔤','🔡','🔠','🆖','🆗','🆙','🆒','🆕',
            '🆓','0️⃣','1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟','🔢','#️⃣','*️⃣','⏏️','▶️','⏸️','⏯️','⏹️','⏺️',
            '⏭️','⏮️','⏩','⏪','⏫','⏬','◀️','🔼','🔽','➡️','⬅️','⬆️','⬇️','↗️','↘️','↙️','↖️','↕️','↔️','↪️',
            '↩️','⤴️','⤵️','🔀','🔁','🔂','🔄','🔃','🎵','🎶','➕','➖','➗','✖️','♾️','💲','💱','™️','©️','®️',
            '〰️','➰','➿','🔚','🔙','🔛','🔝','🔜','✔️','☑️','🔘','🔴','🟠','🟡','🟢','🔵','🟣','⚫','⚪','🟤',
            '🔺','🔻','🔸','🔹','🔶','🔷','🔳','🔲','▪️','▫️','◾','◽','◼️','◻️','🟥','🟧','🟨','🟩','🟦','🟪',
            '⬛','⬜','🟫','🔈','🔇','🔉','🔊','🔔','🔕','📣','📢','💬','💭','🗯️','♠️','♣️','♥️','♦️','🃏','🎴',
            '🀄','🕐','🕑','🕒','🕓','🕔','🕕','🕖','🕗','🕘','🕙','🕚','🕛','🕜','🕝','🕞','🕟','🕠','🕡','🕢',
            '🕣','🕤','🕥','🕦','🕧'
        ];
        this._emojiPickerEl.innerHTML = `
            <div class="emoji-grid">
                ${emojis.map(e => `<span class="emoji-item" data-emoji="${this.escapeHtml(e)}">${this.escapeHtml(e)}</span>`).join('')}
            </div>
        `;
        this._emojiPickerEl.querySelectorAll('.emoji-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const emoji = e.currentTarget.getAttribute('data-emoji');
                const input = document.getElementById('message-input');
                if (input) {
                    input.value = `${input.value || ''}${emoji}`;
                    input.focus();
                }
                this._emojiPickerEl.style.display = 'none';
            });
        });

        const rect = anchorEl.getBoundingClientRect();
        const left = Math.max(8, Math.min(rect.left, window.innerWidth - 280));
        const top = Math.max(8, rect.top - 170);
        this._emojiPickerEl.style.left = `${left}px`;
        this._emojiPickerEl.style.top = `${top}px`;
        this._emojiPickerEl.style.display = 'block';
    }

    toggleChatSearch(show) {
        const bar = document.getElementById('chat-search-bar');
        const input = document.getElementById('chat-search-input');
        const meta = document.getElementById('chat-search-meta');
        if (!bar) return;

        if (show) {
            bar.style.display = 'block';
            if (meta) meta.style.display = 'none';
            if (input) {
                input.value = '';
                input.focus();
            }
        } else {
            bar.style.display = 'none';
        }
    }

    async searchMessages(query) {
        const meta = document.getElementById('chat-search-meta');
        if (!query || !query.trim()) {
            if (meta) meta.style.display = 'none';
            return;
        }
        try {
            const response = await fetch(`/api/communication/search?q=${encodeURIComponent(query)}&other_user_id=${this.activeChatUserId}`, {
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Search failed');
            }
            if (meta) {
                meta.style.display = 'block';
                meta.textContent = `${data.messages.length} result(s)`;
            }
        } catch (e) {
            console.error('Search failed:', e);
        }
    }

    toggleChatSettings(anchorEl) {
        if (!this.activeChatUserId || !this.currentUser) return;
        if (!this._chatSettingsEl) {
            const el = document.createElement('div');
            el.id = 'chat-settings-popover';
            el.style.position = 'fixed';
            el.style.zIndex = '10001';
            el.style.minWidth = '220px';
            el.style.background = '#fff';
            el.style.border = '1px solid rgba(0,0,0,0.12)';
            el.style.borderRadius = '10px';
            el.style.boxShadow = '0 8px 24px rgba(0,0,0,0.18)';
            el.style.padding = '10px';
            el.style.display = 'none';
            document.body.appendChild(el);
            this._chatSettingsEl = el;

            document.addEventListener('click', (e) => {
                if (this._chatSettingsEl && this._chatSettingsEl.style.display === 'block') {
                    if (!this._chatSettingsEl.contains(e.target) && e.target !== anchorEl) {
                        this._chatSettingsEl.style.display = 'none';
                    }
                }
            });
        }

        if (this._chatSettingsEl.style.display === 'block') {
            this._chatSettingsEl.style.display = 'none';
            return;
        }

        const user = this.currentUser;
        const isMuted = !!user.is_muted;
        const isPinned = !!user.is_pinned;
        const isArchived = !!user.is_archived;
        const blockedByMe = !!user.blocked_by_me;

        this._chatSettingsEl.innerHTML = `
            <div style="font-weight:600; font-size:13px; margin-bottom:8px;">Chat Settings</div>
            <div style="display:flex; flex-direction:column; gap:6px;">
                <button type="button" class="btn btn-sm btn-light text-start" data-setting="mute">${isMuted ? 'Unmute' : 'Mute'}</button>
                <button type="button" class="btn btn-sm btn-light text-start" data-setting="pin">${isPinned ? 'Unpin' : 'Pin'}</button>
                <button type="button" class="btn btn-sm btn-light text-start" data-setting="archive">${isArchived ? 'Unarchive' : 'Archive'}</button>
                <button type="button" class="btn btn-sm btn-danger text-start" data-setting="block">${blockedByMe ? 'Unblock user' : 'Block user'}</button>
            </div>
        `;

        this._chatSettingsEl.querySelectorAll('button[data-setting]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const key = e.currentTarget.getAttribute('data-setting');
                this._chatSettingsEl.style.display = 'none';

                if (key === 'block') {
                    await this.toggleBlockUser();
                } else {
                    await this.updateConversationSettings(key);
                }
            });
        });

        const rect = anchorEl.getBoundingClientRect();
        const left = Math.max(8, Math.min(rect.left - 160, window.innerWidth - 260));
        const top = Math.max(8, rect.bottom + 8);
        this._chatSettingsEl.style.left = `${left}px`;
        this._chatSettingsEl.style.top = `${top}px`;
        this._chatSettingsEl.style.display = 'block';
    }

    async updateConversationSettings(key) {
        const user = this.currentUser;
        if (!user) return;

        const patch = {};
        if (key === 'mute') patch.is_muted = !user.is_muted;
        if (key === 'pin') patch.is_pinned = !user.is_pinned;
        if (key === 'archive') patch.is_archived = !user.is_archived;

        try {
            const response = await fetch(`/api/communication/conversation/${user.id}/settings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(patch)
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Failed');

            user.is_muted = data.settings.is_muted;
            user.is_pinned = data.settings.is_pinned;
            user.is_archived = data.settings.is_archived;
            this.currentUser = user;
            await this.loadUsers();
        } catch (e) {
            console.error('Update settings failed:', e);
        }
    }

    async toggleBlockUser() {
        const user = this.currentUser;
        if (!user) return;
        try {
            const response = await fetch(`/api/communication/user/${user.id}/block`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Failed');
            user.blocked_by_me = data.blocked;
            this.currentUser = user;
            this._isChatBlocked = !!(user.blocked_by_me || user.blocked_me);
            this.applyChatBlockedUI();
            await this.loadUsers();
        } catch (e) {
            console.error('Block toggle failed:', e);
        }
    }

    updateUnreadCount(senderId) {
        const userItem = document.querySelector(`.user-item[data-user-id="${senderId}"]`);
        if (userItem) {
            let badge = userItem.querySelector('.unread-badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'unread-badge';
                badge.textContent = '1';
                userItem.appendChild(badge);
            } else {
                badge.textContent = parseInt(badge.textContent) + 1;
            }
        }
        
        // Update float icon badge
        this.updateFloatIconBadge();
    }

    async updateFloatIconBadge() {
        try {
            const response = await fetch('/api/communication/unread_count', {
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) return;
            
            const data = await response.json();
            const badge = document.getElementById('unread-messages-count');
            const floatIcon = document.getElementById('communication-float-icon');
            
            if (badge && floatIcon) {
                if (data.unread_count > 0) {
                    badge.textContent = data.unread_count;
                    badge.style.display = 'block';
                    floatIcon.classList.add('has-unread');
                } else {
                    badge.style.display = 'none';
                    floatIcon.classList.remove('has-unread');
                }
            }
        } catch (error) {
            console.error('Error updating unread count:', error);
        }
    }

    // Call functionality
    async initiateCall(type) {
        if (!this.activeChatUserId) return;
        
        this.callType = type;
        this._callRole = 'caller';
        
        try {
            // Request media permissions
            const constraints = {
                audio: true,
                video: type === 'video'
            };
            
            this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Create call record
            const response = await fetch('/api/communication/initiate_call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    receiver_id: this.activeChatUserId,
                    call_type: type
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to initiate call');
            }
            
            const data = await response.json();
            this.callId = data.call_id;
            
            // Emit call signal
            this.socket.emit('initiate_call', {
                receiver_id: this.activeChatUserId,
                call_type: type,
                call_id: this.callId,
                caller_name: 'You'
            });
            
            // Show call UI (waiting for answer)
            this.showCallUI(type, 'outgoing');
            this.playOutgoingTone();
            
        } catch (error) {
            console.error('Error initiating call:', error);
            this.showError('Failed to initiate call. Please check your media permissions.');
        }
    }

    handleIncomingCall(data) {
        this.callId = data.call_id;
        this.callType = data.call_type;
        this.activeChatUserId = data.caller_id;
        this._callRole = 'callee';

        // Ensure we have a currentUser context for call UI
        this.currentUser = {
            id: data.caller_id,
            username: data.caller_name || 'Unknown',
            is_online: true
        };
        
        // Show incoming call UI
        const callModal = document.getElementById('call-modal');
        const incomingCall = document.getElementById('incoming-call');
        
        if (callModal && incomingCall) {
            callModal.style.display = 'flex';
            incomingCall.style.display = 'block';
            
            document.getElementById('incoming-caller-name').textContent = data.caller_name || 'Unknown';
            document.getElementById('incoming-call-type').textContent = 
                `Incoming ${data.call_type === 'video' ? 'Video' : 'Voice'} Call`;
        }
        
        // Play ringtone (optional)
        this.playRingtone();
    }

    async acceptCall() {
        try {
            this.stopAllTones();
            // Request media permissions
            const constraints = {
                audio: true,
                video: this.callType === 'video'
            };
            
            this.localStream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Update call status
            await fetch('/api/communication/answer_call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    call_id: this.callId
                })
            });
            
            // Emit accept signal
            this.socket.emit('accept_call', {
                call_id: this.callId,
                receiver_id: this.activeChatUserId
            });
            
            // Setup peer connection (callee waits for offer)
            await this.ensurePeerConnection();
            
            // Show active call UI
            this.showCallUI(this.callType, 'active');
            
        } catch (error) {
            console.error('Error accepting call:', error);
            this.showError('Failed to accept call');
        }
    }

    async rejectCall() {
        try {
            this.stopAllTones();
            await fetch('/api/communication/reject_call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    call_id: this.callId
                })
            });
            
            this.socket.emit('reject_call', {
                call_id: this.callId,
                receiver_id: this.activeChatUserId
            });
            
            this.hideCallUI();
            this.cleanupCall();
            
        } catch (error) {
            console.error('Error rejecting call:', error);
        }
    }

    async endCall() {
        try {
            this.stopAllTones();
            await fetch('/api/communication/end_call', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    call_id: this.callId
                })
            });
            
            this.socket.emit('end_call', {
                call_id: this.callId,
                receiver_id: this.activeChatUserId
            });
            
            this.cleanupCall();
            
        } catch (error) {
            console.error('Error ending call:', error);
        }
    }

    handleCallAccepted(data) {
        this.stopAllTones();
        // Caller starts WebRTC offer after callee accepts
        this.startCallerWebRTC();
        this.showCallUI(this.callType, 'active');
    }

    handleCallRejected(data) {
        this.stopAllTones();
        this.showError('Call was rejected');
        this.cleanupCall();
    }

    handleCallEnded(data) {
        this.stopAllTones();
        this.cleanupCall();
    }

    async fetchIceServers() {
        if (this._iceServersCache) return this._iceServersCache;
        try {
            const response = await fetch('/api/communication/ice_servers', {
                headers: { 'X-CSRFToken': this.getCSRFToken() }
            });
            if (response.ok) {
                const data = await response.json();
                if (data && Array.isArray(data.ice_servers) && data.ice_servers.length) {
                    this._iceServersCache = data.ice_servers;
                    return this._iceServersCache;
                }
            }
        } catch (e) {
            // fall back
        }
        this._iceServersCache = [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ];
        return this._iceServersCache;
    }

    async ensurePeerConnection() {
        if (this.peerConnection) return;

        const iceServers = await this.fetchIceServers();
        const configuration = { iceServers };

        this.peerConnection = new RTCPeerConnection(configuration);

        if (this.localStream) {
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });
        }

        this.peerConnection.ontrack = (event) => {
            if (event.streams && event.streams[0]) {
                this.remoteStream = event.streams[0];
                const remoteVideo = document.getElementById('remote-video');
                if (remoteVideo) remoteVideo.srcObject = this.remoteStream;
            }
        };

        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.socket.emit('webrtc_ice_candidate', {
                    candidate: event.candidate,
                    receiver_id: this.activeChatUserId,
                    call_id: this.callId
                });
            }
        };
    }

    async startCallerWebRTC() {
        try {
            this._callRole = 'caller';
            await this.ensurePeerConnection();
            if (!this.peerConnection) return;

            const offer = await this.peerConnection.createOffer({
                offerToReceiveAudio: true,
                offerToReceiveVideo: this.callType === 'video'
            });
            await this.peerConnection.setLocalDescription(offer);

            this.socket.emit('webrtc_offer', {
                offer,
                receiver_id: this.activeChatUserId,
                call_id: this.callId
            });
        } catch (e) {
            console.error('Error starting caller WebRTC:', e);
            this.showError('WebRTC failed to start. Please try again.');
        }
    }

    async handleWebRTCOffer(data) {
        try {
            // Callee receives offer, creates answer
            if (!this.peerConnection) {
                await this.ensurePeerConnection();
            }
            if (!this.peerConnection) return;

            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));

            const answer = await this.peerConnection.createAnswer();
            await this.peerConnection.setLocalDescription(answer);

            this.socket.emit('webrtc_answer', {
                answer,
                receiver_id: data.caller_id,
                call_id: data.call_id || this.callId
            });
        } catch (e) {
            console.error('Error handling WebRTC offer:', e);
        }
    }

    async handleWebRTCAnswer(data) {
        if (this.peerConnection) {
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
        }
    }

    async handleWebRTCIceCandidate(data) {
        if (this.peerConnection && data.candidate) {
            try {
                await this.peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            } catch (error) {
                console.error('Error adding ICE candidate:', error);
            }
        }
    }

    showCallUI(type, status) {
        const callModal = document.getElementById('call-modal');
        const outgoingCall = document.getElementById('outgoing-call');
        const incomingCall = document.getElementById('incoming-call');
        const activeCall = document.getElementById('active-call');
        const videoContainer = document.getElementById('video-container');
        const voiceCallDisplay = document.getElementById('voice-call-display');
        const toggleVideoBtn = document.getElementById('toggle-video-btn');
        
        if (!callModal || !activeCall) return;
        
        callModal.style.display = 'flex';

        // Reset sections
        if (outgoingCall) outgoingCall.style.display = 'none';
        if (incomingCall) incomingCall.style.display = 'none';
        activeCall.style.display = 'none';
        
        if (status === 'outgoing') {
            if (outgoingCall) outgoingCall.style.display = 'block';
            const calleeName = document.getElementById('outgoing-callee-name');
            const outgoingStatus = document.getElementById('outgoing-call-status');
            if (calleeName) calleeName.textContent = this.currentUser?.username || 'User';
            if (outgoingStatus) outgoingStatus.textContent = type === 'video' ? 'Calling (video)...' : 'Calling...';
            return;
        }

        if (status === 'active') {
            activeCall.style.display = 'block';
            
            if (type === 'video') {
                videoContainer.style.display = 'block';
                voiceCallDisplay.style.display = 'none';
                toggleVideoBtn.style.display = 'block';
                
                // Set local video
                const localVideo = document.getElementById('local-video');
                if (localVideo && this.localStream) {
                    localVideo.srcObject = this.localStream;
                }
            } else {
                videoContainer.style.display = 'none';
                voiceCallDisplay.style.display = 'block';
                toggleVideoBtn.style.display = 'none';
                
                document.getElementById('active-caller-name').textContent = 
                    this.currentUser?.username || 'Unknown';
            }
            
            // Start call duration timer
            this.startCallDurationTimer();
        }
    }

    hideCallUI() {
        const callModal = document.getElementById('call-modal');
        if (callModal) {
            callModal.style.display = 'none';
        }
    }

    startCallDurationTimer() {
        let seconds = 0;
        this.callDurationInterval = setInterval(() => {
            seconds++;
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
            const durationText = `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            
            const durationElement = document.getElementById('call-duration');
            if (durationElement) {
                durationElement.textContent = durationText;
            }
        }, 1000);
    }

    toggleMute() {
        if (!this.localStream) return;
        
        const audioTrack = this.localStream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = !audioTrack.enabled;
            this.isMuted = !audioTrack.enabled;
            
            const muteBtn = document.getElementById('mute-btn');
            if (muteBtn) {
                const icon = muteBtn.querySelector('i');
                if (icon) {
                    icon.className = this.isMuted ? 'bi bi-mic-mute-fill' : 'bi bi-mic-fill';
                }
            }
        }
    }

    toggleVideo() {
        if (!this.localStream) return;
        
        const videoTrack = this.localStream.getVideoTracks()[0];
        if (videoTrack) {
            videoTrack.enabled = !videoTrack.enabled;
            this.isVideoEnabled = videoTrack.enabled;
            
            const toggleVideoBtn = document.getElementById('toggle-video-btn');
            if (toggleVideoBtn) {
                const icon = toggleVideoBtn.querySelector('i');
                if (icon) {
                    icon.className = this.isVideoEnabled ? 'bi bi-camera-video-fill' : 'bi bi-camera-video-off-fill';
                }
            }
        }
    }

    cleanupCall() {
        this.stopAllTones();
        // Stop all tracks
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }
        
        if (this.remoteStream) {
            this.remoteStream.getTracks().forEach(track => track.stop());
            this.remoteStream = null;
        }
        
        // Close peer connection
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        // Clear call duration timer
        if (this.callDurationInterval) {
            clearInterval(this.callDurationInterval);
            this.callDurationInterval = null;
        }
        
        // Hide call UI
        this.hideCallUI();
        
        // Reset call state
        this.callId = null;
        this.callType = null;
        this._callRole = null;
        this.isMuted = false;
        this.isVideoEnabled = true;
    }

    playRingtone() {
        this.stopAllTones();
        this._toneStopFn = this.startBeepPattern({
            frequency: 440,
            onMs: 700,
            offMs: 1300,
            gain: 0.08
        });
    }

    playOutgoingTone() {
        this.stopAllTones();
        this._toneStopFn = this.startBeepPattern({
            frequency: 480,
            onMs: 180,
            offMs: 180,
            gain: 0.05
        });
    }

    stopAllTones() {
        if (this._toneStopFn) {
            try { this._toneStopFn(); } catch (_) {}
            this._toneStopFn = null;
        }
    }

    startBeepPattern({ frequency, onMs, offMs, gain }) {
        if (!this._audioContext) return () => {};

        let stopped = false;
        let osc = null;
        let g = null;
        let timer = null;

        const startOsc = () => {
            if (stopped) return;
            try {
                osc = this._audioContext.createOscillator();
                g = this._audioContext.createGain();
                osc.type = 'sine';
                osc.frequency.value = frequency;
                g.gain.value = gain;
                osc.connect(g);
                g.connect(this._audioContext.destination);
                osc.start();
                timer = setTimeout(stopOsc, onMs);
            } catch (_) {
                // no-op
            }
        };

        const stopOsc = () => {
            if (stopped) return;
            try {
                if (osc) {
                    osc.stop();
                    osc.disconnect();
                    osc = null;
                }
                if (g) {
                    g.disconnect();
                    g = null;
                }
            } catch (_) {
                // no-op
            }
            timer = setTimeout(startOsc, offMs);
        };

        startOsc();

        return () => {
            stopped = true;
            if (timer) clearTimeout(timer);
            try {
                if (osc) {
                    osc.stop();
                    osc.disconnect();
                }
                if (g) g.disconnect();
            } catch (_) {}
        };
    }

    requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    showNotification(message) {
        if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification('New Message', {
                body: message.content,
                icon: '/static/images/icon-192.png',
                badge: '/static/images/icon-192.png'
            });
            
            notification.onclick = () => {
                window.focus();
                this.toggleCommunicationModal();
                // Open chat with sender
                const userItem = document.querySelector(`.user-item[data-user-id="${message.sender_id}"]`);
                if (userItem) {
                    userItem.click();
                }
            };
        }
    }

    showError(message) {
        // You can implement a better error display mechanism
        console.error(message);
        alert(message);
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    formatTimeEAT(dateString) {
        /**
         * Format time to EAT (East Africa Time) timezone
         * Converts ISO timestamp to EAT and displays in 24-hour HH:MM format
         */
        try {
            // Parse the ISO string to Date object
            const date = new Date(dateString);
            
            // Get time in EAT timezone using Intl.DateTimeFormat
            const eatTime = new Intl.DateTimeFormat('en-GB', {
                timeZone: this.eatTimezone,
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            }).format(date);
            
            return eatTime;
        } catch (error) {
            console.error('Error formatting time:', error);
            // Fallback to local time if timezone conversion fails
            const date = new Date(dateString);
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            return `${hours}:${minutes}`;
        }
    }

    formatDateTimeEAT(dateString) {
        /**
         * Format full date and time to EAT timezone
         * Used for detailed timestamps
         */
        try {
            const date = new Date(dateString);
            
            return date.toLocaleString('en-US', {
                timeZone: this.eatTimezone,
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            });
        } catch (error) {
            console.error('Error formatting datetime:', error);
            return new Date(dateString).toLocaleString();
        }
    }

    setupDragFunctionality() {
        const modal = document.getElementById('communication-modal');
        const dragHandle = document.getElementById('communication-drag-handle');
        
        if (!modal || !dragHandle) return;
        
        // Disable drag on mobile devices
        if (window.innerWidth <= 767) {
            return;
        }
        
        let isDragging = false;
        let currentX;
        let currentY;
        let initialX;
        let initialY;
        let xOffset = 0;
        let yOffset = 0;

        // Mouse events
        dragHandle.addEventListener('mousedown', dragStart);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', dragEnd);

        // Touch events for tablets
        dragHandle.addEventListener('touchstart', touchStart, { passive: false });
        document.addEventListener('touchmove', touchMove, { passive: false });
        document.addEventListener('touchend', touchEnd);

        function dragStart(e) {
            // Don't drag if clicking on buttons or on mobile
            if (e.target.closest('button') || window.innerWidth <= 767) return;
            
            initialX = e.clientX - xOffset;
            initialY = e.clientY - yOffset;

            if (e.target === dragHandle || dragHandle.contains(e.target)) {
                isDragging = true;
            }
        }

        function touchStart(e) {
            // Don't drag on mobile
            if (window.innerWidth <= 767) return;
            if (e.target.closest('button')) return;

            const touch = e.touches[0];
            initialX = touch.clientX - xOffset;
            initialY = touch.clientY - yOffset;

            if (e.target === dragHandle || dragHandle.contains(e.target)) {
                isDragging = true;
            }
        }

        function drag(e) {
            if (isDragging && window.innerWidth > 767) {
                e.preventDefault();
                
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;

                xOffset = currentX;
                yOffset = currentY;

                // Update modal position
                modal.style.transform = `translate(calc(-50% + ${currentX}px), calc(-50% + ${currentY}px))`;
            }
        }

        function touchMove(e) {
            if (isDragging && window.innerWidth > 767) {
                e.preventDefault();
                
                const touch = e.touches[0];
                currentX = touch.clientX - initialX;
                currentY = touch.clientY - initialY;

                xOffset = currentX;
                yOffset = currentY;

                // Update modal position
                modal.style.transform = `translate(calc(-50% + ${currentX}px), calc(-50% + ${currentY}px))`;
            }
        }

        function dragEnd(e) {
            initialX = currentX;
            initialY = currentY;
            isDragging = false;
        }

        function touchEnd(e) {
            dragEnd(e);
        }

        // Re-check on window resize
        window.addEventListener('resize', () => {
            if (window.innerWidth <= 767) {
                isDragging = false;
                // Reset position for mobile
                modal.style.transform = '';
            }
        });
    }
}

// Initialize communication system when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.communicationSystem = new CommunicationSystem();
});
