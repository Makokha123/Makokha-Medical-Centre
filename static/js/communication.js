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
        this.loadingMore = false;
        this.isScreenSharing = false;
        this.currentGroupId = null;
        
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

        // Group chat events
        this.socket.on('group_message', (data) => {
            this.handleGroupMessage(data);
        });

        // Screen sharing events
        this.socket.on('screen_share_started', (data) => {
            this.handleScreenShareStarted(data);
        });

        this.socket.on('screen_share_stopped', (data) => {
            this.handleScreenShareStopped(data);
        });

        // Message edit/delete events
        this.socket.on('message_edited', (data) => {
            this.handleMessageEdited(data);
        });

        this.socket.on('message_deleted', (data) => {
            this.handleMessageDeleted(data);
        });

        // Reaction events
        this.socket.on('message_reacted', (data) => {
            this.handleMessageReacted(data);
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
        
        if (muteBtn) {
            muteBtn.addEventListener('click', () => this.toggleMute());
        }
        
        if (toggleVideoBtn) {
            toggleVideoBtn.addEventListener('click', () => this.toggleVideo());
        }

        // File upload
        const attachFileBtn = document.getElementById('attach-file-btn');
        const fileInput = document.getElementById('file-input');
        
        if (attachFileBtn && fileInput) {
            attachFileBtn.addEventListener('click', () => fileInput.click());
            
            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                
                try {
                    this.showLoading('Uploading file...');
                    const uploadData = await this.uploadFile(file);
                    await this.sendFileMessage(uploadData);
                    this.hideLoading();
                    e.target.value = '';
                    this.showNotification('File sent successfully');
                } catch (error) {
                    this.hideLoading();
                    this.showError('Failed to upload file');
                }
            });
        }

        // Message search
        const searchMessagesInput = document.getElementById('message-search');
        if (searchMessagesInput) {
            let searchTimeout;
            searchMessagesInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.searchMessages(e.target.value);
                }, 300);
            });
        }

        // Pagination - scroll to load more
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.addEventListener('scroll', () => {
                if (messagesContainer.scrollTop === 0 && !this.loadingMore && this.activeChatUserId) {
                    const firstMessage = messagesContainer.querySelector('.message');
                    if (firstMessage) {
                        const messageId = firstMessage.dataset.messageId;
                        this.loadMoreMessages(messageId);
                    }
                }
            });
        }

        // Screen share button
        const screenShareBtn = document.getElementById('screen-share-btn');
        if (screenShareBtn) {
            screenShareBtn.addEventListener('click', () => {
                if (this.isScreenSharing) {
                    this.stopScreenShare();
                } else {
                    this.startScreenShare();
                }
            });
        }

        // Mobile responsive handlers
        this.setupMobileHandlers();
    }

    setupMobileHandlers() {
        // Add back button functionality for mobile
        const chatHeader = document.querySelector('.chat-header');
        if (chatHeader && window.innerWidth <= 767) {
            chatHeader.style.cursor = 'pointer';
            chatHeader.addEventListener('click', (e) => {
                if (e.target.closest('.chat-actions')) return;
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
        
        users.forEach(user => {
            const userItem = document.createElement('div');
            userItem.className = 'user-item';
            userItem.dataset.userId = user.id;
            
            const onlineBadge = user.is_online ? '<span class="online-badge"></span>' : '';
            
            userItem.innerHTML = `
                <div class="user-avatar">
                    <i class="bi bi-person-circle"></i>
                    ${onlineBadge}
                </div>
                <div class="user-info">
                    <div class="user-name">${this.escapeHtml(user.username)}</div>
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
        statusElement.textContent = user.is_online ? 'online' : 'offline';
        statusElement.className = user.is_online ? 'text-success' : 'text-muted';
        
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
        
        messageDiv.innerHTML = `
            <div class="message-bubble">
                <div class="message-content">${this.escapeHtml(message.content)}</div>
                <div class="message-time">
                    ${time}
                    ${tickMarks}
                </div>
            </div>
        `;
        
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
        
        try {
            const response = await fetch('/api/communication/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    receiver_id: this.activeChatUserId,
                    content: content
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to send message');
            }
            
            const data = await response.json();
            
            // Clear input
            messageInput.value = '';
            
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

    handleMessageRead(data) {
        // Update UI to show message as read
        console.log('Message read:', data);
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
                statusElement.textContent = data.is_online ? 'online' : 'offline';
                statusElement.className = data.is_online ? 'text-success' : 'text-muted';
            }
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
            
        } catch (error) {
            console.error('Error initiating call:', error);
            this.showError('Failed to initiate call. Please check your media permissions.');
        }
    }

    handleIncomingCall(data) {
        this.callId = data.call_id;
        this.callType = data.call_type;
        this.activeChatUserId = data.caller_id;
        
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
            
            // Setup WebRTC connection
            await this.setupWebRTCConnection();
            
            // Show active call UI
            this.showCallUI(this.callType, 'active');
            
        } catch (error) {
            console.error('Error accepting call:', error);
            this.showError('Failed to accept call');
        }
    }

    async rejectCall() {
        try {
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
            
        } catch (error) {
            console.error('Error rejecting call:', error);
        }
    }

    async endCall() {
        try {
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
        // Setup WebRTC connection
        this.setupWebRTCConnection();
        this.showCallUI(this.callType, 'active');
    }

    handleCallRejected(data) {
        this.showError('Call was rejected');
        this.cleanupCall();
    }

    handleCallEnded(data) {
        this.cleanupCall();
    }

    async setupWebRTCConnection() {
        // ICE servers configuration (STUN/TURN servers)
        const configuration = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' }
            ]
        };
        
        this.peerConnection = new RTCPeerConnection(configuration);
        
        // Add local stream to peer connection
        this.localStream.getTracks().forEach(track => {
            this.peerConnection.addTrack(track, this.localStream);
        });
        
        // Handle remote stream
        this.peerConnection.ontrack = (event) => {
            if (event.streams && event.streams[0]) {
                this.remoteStream = event.streams[0];
                const remoteVideo = document.getElementById('remote-video');
                if (remoteVideo) {
                    remoteVideo.srcObject = this.remoteStream;
                }
            }
        };
        
        // Handle ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.socket.emit('webrtc_ice_candidate', {
                    candidate: event.candidate,
                    receiver_id: this.activeChatUserId,
                    call_id: this.callId
                });
            }
        };
        
        // Create and send offer
        const offer = await this.peerConnection.createOffer();
        await this.peerConnection.setLocalDescription(offer);
        
        this.socket.emit('webrtc_offer', {
            offer: offer,
            receiver_id: this.activeChatUserId,
            call_id: this.callId
        });
    }

    async handleWebRTCOffer(data) {
        // Create peer connection if not exists
        if (!this.peerConnection) {
            await this.setupWebRTCConnection();
        }
        
        await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
        
        const answer = await this.peerConnection.createAnswer();
        await this.peerConnection.setLocalDescription(answer);
        
        this.socket.emit('webrtc_answer', {
            answer: answer,
            receiver_id: data.caller_id,
            call_id: this.callId
        });
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
        const incomingCall = document.getElementById('incoming-call');
        const activeCall = document.getElementById('active-call');
        const videoContainer = document.getElementById('video-container');
        const voiceCallDisplay = document.getElementById('voice-call-display');
        const toggleVideoBtn = document.getElementById('toggle-video-btn');
        
        if (!callModal || !activeCall) return;
        
        callModal.style.display = 'flex';
        
        if (status === 'active') {
            if (incomingCall) incomingCall.style.display = 'none';
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
        this.isMuted = false;
        this.isVideoEnabled = true;
    }

    playRingtone() {
        // Optional: Play ringtone sound
        // You can implement this with HTML5 Audio API
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

    showLoading(message = 'Loading...') {
        let loader = document.getElementById('comm-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'comm-loader';
            loader.style.cssText = `
                position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                background: rgba(0,0,0,0.8); color: white; padding: 20px 40px;
                border-radius: 8px; z-index: 10000; display: flex; align-items: center; gap: 15px;
            `;
            loader.innerHTML = `
                <div class="spinner-border spinner-border-sm" role="status"></div>
                <span id="loader-text">${message}</span>
            `;
            document.body.appendChild(loader);
        } else {
            loader.style.display = 'flex';
            loader.querySelector('#loader-text').textContent = message;
        }
    }

    hideLoading() {
        const loader = document.getElementById('comm-loader');
        if (loader) {
            loader.style.display = 'none';
        }
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

    // ==========================================
    // FILE UPLOAD & MEDIA
    // ==========================================

    async uploadFile(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/communication/upload', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: formData
            });
            
            if (!response.ok) throw new Error('Upload failed');
            
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Upload error:', error);
            throw error;
        }
    }

    async sendFileMessage(uploadData) {
        try {
            const response = await fetch('/api/communication/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    receiver_id: this.activeChatUserId,
                    content: uploadData.file_name,
                    message_type: uploadData.message_type,
                    file_url: uploadData.file_url,
                    file_name: uploadData.file_name,
                    file_size: uploadData.file_size
                })
            });
            
            if (!response.ok) throw new Error('Failed to send file message');
            
            const data = await response.json();
            
            // Emit to Socket.IO
            this.socket.emit('send_message', {
                message: data.message,
                receiver_id: this.activeChatUserId
            });
            
            this.appendMessage(data.message);
            
            return data;
        } catch (error) {
            console.error('Error sending file message:', error);
            throw error;
        }
    }

    // ==========================================
    // MESSAGE EDITING & DELETION
    // ==========================================

    async editMessage(messageId, newContent) {
        try {
            const response = await fetch(`/api/communication/message/${messageId}/edit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({content: newContent})
            });
            
            if (!response.ok) throw new Error('Edit failed');
            
            const data = await response.json();
            
            // Update UI
            const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageDiv) {
                const contentEl = messageDiv.querySelector('.message-content');
                if (contentEl) {
                    contentEl.textContent = newContent;
                }
                
                const timeEl = messageDiv.querySelector('.message-time');
                if (timeEl && !timeEl.querySelector('.edited-indicator')) {
                    timeEl.insertAdjacentHTML('beforeend', ' <span class="edited-indicator text-muted">(edited)</span>');
                }
            }
            
            return data;
        } catch (error) {
            console.error('Edit error:', error);
            this.showError('Failed to edit message');
            throw error;
        }
    }

    async deleteMessage(messageId) {
        try {
            if (!confirm('Delete this message?')) return;
            
            const response = await fetch(`/api/communication/message/${messageId}/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) throw new Error('Delete failed');
            
            const data = await response.json();
            
            // Update UI
            const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageDiv) {
                const contentEl = messageDiv.querySelector('.message-content');
                if (contentEl) {
                    contentEl.textContent = '[Message deleted]';
                    contentEl.style.fontStyle = 'italic';
                    contentEl.style.opacity = '0.6';
                }
                
                // Remove actions
                const actionsEl = messageDiv.querySelector('.message-actions');
                if (actionsEl) {
                    actionsEl.remove();
                }
            }
            
            return data;
        } catch (error) {
            console.error('Delete error:', error);
            this.showError('Failed to delete message');
            throw error;
        }
    }

    async starMessage(messageId) {
        try {
            const response = await fetch(`/api/communication/message/${messageId}/star`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) throw new Error('Star failed');
            
            const data = await response.json();
            
            // Update UI
            const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageDiv) {
                const starBtn = messageDiv.querySelector('.star-btn');
                if (starBtn) {
                    if (data.is_starred) {
                        starBtn.classList.add('text-warning');
                        starBtn.innerHTML = '<i class="bi bi-star-fill"></i>';
                    } else {
                        starBtn.classList.remove('text-warning');
                        starBtn.innerHTML = '<i class="bi bi-star"></i>';
                    }
                }
            }
            
            return data;
        } catch (error) {
            console.error('Star error:', error);
            throw error;
        }
    }

    // ==========================================
    // MESSAGE REACTIONS
    // ==========================================

    async reactToMessage(messageId, emoji) {
        try {
            const response = await fetch(`/api/communication/message/${messageId}/react`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({emoji})
            });
            
            if (!response.ok) throw new Error('React failed');
            
            const data = await response.json();
            
            // Update reactions UI
            this.updateReactionsDisplay(messageId, data.reactions);
            
            return data;
        } catch (error) {
            console.error('React error:', error);
            throw error;
        }
    }

    updateReactionsDisplay(messageId, reactions) {
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageDiv) return;
        
        let reactionsEl = messageDiv.querySelector('.message-reactions');
        if (!reactionsEl) {
            reactionsEl = document.createElement('div');
            reactionsEl.className = 'message-reactions mt-1';
            messageDiv.querySelector('.message-bubble').appendChild(reactionsEl);
        }
        
        reactionsEl.innerHTML = '';
        
        if (reactions && Object.keys(reactions).length > 0) {
            for (const [emoji, users] of Object.entries(reactions)) {
                if (users.length > 0) {
                    const reactionBtn = document.createElement('button');
                    reactionBtn.className = 'btn btn-sm btn-light me-1 mb-1';
                    reactionBtn.innerHTML = `${emoji} ${users.length}`;
                    reactionBtn.onclick = () => this.reactToMessage(messageId, emoji);
                    reactionsEl.appendChild(reactionBtn);
                }
            }
        }
    }

    showEmojiPicker(messageId) {
        // Simple emoji picker
        const emojis = ['👍', '❤️', '😂', '😮', '😢', '🙏', '🔥', '👏'];
        
        const pickerHTML = `
            <div class="emoji-picker-dropdown" style="position: absolute; z-index: 1000; 
                 background: white; border: 1px solid #ddd; border-radius: 8px; padding: 10px; 
                 box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                ${emojis.map(emoji => `
                    <button class="btn btn-sm btn-light m-1" onclick="window.communicationSystem.reactToMessage('${messageId}', '${emoji}'); this.parentElement.remove();">
                        ${emoji}
                    </button>
                `).join('')}
            </div>
        `;
        
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (messageDiv) {
            // Remove existing picker
            const existingPicker = document.querySelector('.emoji-picker-dropdown');
            if (existingPicker) existingPicker.remove();
            
            messageDiv.insertAdjacentHTML('beforeend', pickerHTML);
            
            // Close on outside click
            setTimeout(() => {
                document.addEventListener('click', function closePicker(e) {
                    if (!e.target.closest('.emoji-picker-dropdown') && !e.target.closest('.react-btn')) {
                        const picker = document.querySelector('.emoji-picker-dropdown');
                        if (picker) picker.remove();
                        document.removeEventListener('click', closePicker);
                    }
                }, 100);
            });
        }
    }

    // ==========================================
    // GROUP CHATS
    // ==========================================

    async loadGroups() {
        try {
            const response = await fetch('/api/communication/groups', {
                headers: {'X-CSRFToken': this.getCSRFToken()}
            });
            
            if (!response.ok) throw new Error('Failed to load groups');
            
            const data = await response.json();
            this.displayGroups(data.groups);
        } catch (error) {
            console.error('Error loading groups:', error);
        }
    }

    displayGroups(groups) {
        const groupsList = document.getElementById('groups-list');
        if (!groupsList) return;
        
        if (groups.length === 0) {
            groupsList.innerHTML = '<p class="text-muted text-center py-3">No groups yet</p>';
            return;
        }
        
        const html = groups.map(group => `
            <div class="group-item p-3 border-bottom cursor-pointer" onclick="window.communicationSystem.openGroup('${group.group_id}')">
                <div class="d-flex align-items-center">
                    <div class="group-avatar me-3">
                        <i class="bi bi-people-fill fs-4"></i>
                    </div>
                    <div class="flex-grow-1">
                        <strong>${group.name}</strong>
                        <p class="text-muted small mb-0">${group.member_count} members</p>
                    </div>
                </div>
            </div>
        `).join('');
        
        groupsList.innerHTML = html;
    }

    async createGroup(name, description, memberIds) {
        try {
            const response = await fetch('/api/communication/groups/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    name,
                    description,
                    members: memberIds
                })
            });
            
            if (!response.ok) throw new Error('Failed to create group');
            
            const data = await response.json();
            
            // Join group room
            this.socket.emit('join_group', {group_id: data.group.group_id});
            
            this.showNotification(`Group "${name}" created successfully`);
            await this.loadGroups();
            
            return data.group;
        } catch (error) {
            console.error('Error creating group:', error);
            this.showError('Failed to create group');
            throw error;
        }
    }

    async openGroup(groupId) {
        this.currentGroupId = groupId;
        
        // Load group messages
        await this.loadGroupMessages(groupId);
        
        // Show group chat UI
        // (Implementation depends on your UI design)
    }

    async loadGroupMessages(groupId, page = 1) {
        try {
            const response = await fetch(`/api/communication/groups/${groupId}/messages?page=${page}`, {
                headers: {'X-CSRFToken': this.getCSRFToken()}
            });
            
            if (!response.ok) throw new Error('Failed to load group messages');
            
            const data = await response.json();
            this.displayGroupMessages(data.messages);
        } catch (error) {
            console.error('Error loading group messages:', error);
        }
    }

    displayGroupMessages(messages) {
        const container = document.getElementById('group-messages-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        messages.forEach(msg => {
            this.appendGroupMessage(msg);
        });
        
        container.scrollTop = container.scrollHeight;
    }

    appendGroupMessage(message) {
        const container = document.getElementById('group-messages-container');
        if (!container) return;
        
        const isOwn = message.sender_id === this.currentUserId;
        
        const messageHTML = `
            <div class="message ${isOwn ? 'sent' : 'received'}" data-message-id="${message.message_id}">
                <div class="message-bubble">
                    ${!isOwn ? `<strong class="text-primary">${message.sender.username}</strong><br>` : ''}
                    <div class="message-content">${this.escapeHtml(message.content)}</div>
                    <div class="message-time text-muted small">${this.formatTime(message.created_at)}</div>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', messageHTML);
        container.scrollTop = container.scrollHeight;
    }

    async sendGroupMessage(groupId, content, messageType = 'text') {
        try {
            const response = await fetch(`/api/communication/groups/${groupId}/send`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    content,
                    message_type: messageType
                })
            });
            
            if (!response.ok) throw new Error('Failed to send group message');
            
            return await response.json();
        } catch (error) {
            console.error('Error sending group message:', error);
            this.showError('Failed to send message');
            throw error;
        }
    }

    handleGroupMessage(data) {
        console.log('Group message received:', data);
        if (this.currentGroupId === data.group_id) {
            this.appendGroupMessage(data.message);
        }
        this.showNotification(`New message in ${data.group_name}`);
    }

    // ==========================================
    // SEARCH FUNCTIONALITY
    // ==========================================

    async searchMessages(query) {
        if (!query || query.trim().length < 2) {
            document.getElementById('search-results').innerHTML = '';
            return;
        }
        
        try {
            const response = await fetch(`/api/communication/search?q=${encodeURIComponent(query)}`, {
                headers: {'X-CSRFToken': this.getCSRFToken()}
            });
            
            if (!response.ok) throw new Error('Search failed');
            
            const data = await response.json();
            this.displaySearchResults(data.messages);
        } catch (error) {
            console.error('Search error:', error);
        }
    }

    displaySearchResults(messages) {
        const resultsContainer = document.getElementById('search-results');
        if (!resultsContainer) return;
        
        if (messages.length === 0) {
            resultsContainer.innerHTML = '<p class="text-muted text-center py-3">No messages found</p>';
            return;
        }
        
        const html = messages.map(msg => `
            <div class="search-result-item p-2 border-bottom cursor-pointer" 
                 onclick="window.communicationSystem.goToMessage('${msg.message_id}', ${msg.sender_id})">
                <strong>${msg.sender.username}</strong>
                <p class="mb-0 small">${this.escapeHtml(msg.content).substring(0, 100)}...</p>
                <span class="text-muted small">${this.formatTimeAgo(msg.created_at)}</span>
            </div>
        `).join('');
        
        resultsContainer.innerHTML = html;
    }

    async goToMessage(messageId, senderId) {
        // Open conversation with sender
        await this.openChatById(senderId);
        
        // Scroll to message
        setTimeout(() => {
            const messageEl = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageEl) {
                messageEl.scrollIntoView({behavior: 'smooth', block: 'center'});
                messageEl.classList.add('highlight-message');
                setTimeout(() => messageEl.classList.remove('highlight-message'), 2000);
            }
        }, 500);
    }

    async openChatById(userId) {
        // Find user in list
        const userItem = document.querySelector(`[data-user-id="${userId}"]`);
        if (userItem) {
            userItem.click();
        } else {
            // Load user data and open chat
            try {
                const response = await fetch(`/api/user/${userId}`, {
                    headers: {'X-CSRFToken': this.getCSRFToken()}
                });
                const user = await response.json();
                await this.openChat(user);
            } catch (error) {
                console.error('Error opening chat:', error);
            }
        }
    }

    // ==========================================
    // PAGINATION
    // ==========================================

    async loadMoreMessages(beforeMessageId) {
        if (this.loadingMore) return;
        
        this.loadingMore = true;
        
        try {
            const response = await fetch(
                `/api/communication/conversation/${this.activeChatUserId}/paginated?before_id=${beforeMessageId}&per_page=50`,
                {headers: {'X-CSRFToken': this.getCSRFToken()}}
            );
            
            if (!response.ok) throw new Error('Failed to load more messages');
            
            const data = await response.json();
            
            const container = document.getElementById('messages-container');
            const scrollHeight = container.scrollHeight;
            
            // Prepend older messages
            data.messages.reverse().forEach(msg => this.prependMessage(msg));
            
            // Maintain scroll position
            container.scrollTop = container.scrollHeight - scrollHeight;
            
            return data.has_more;
        } catch (error) {
            console.error('Pagination error:', error);
        } finally {
            this.loadingMore = false;
        }
    }

    prependMessage(message) {
        const container = document.getElementById('messages-container');
        if (!container) return;
        
        const isOwn = message.sender_id === this.currentUserId;
        
        const messageHTML = `
            <div class="message ${isOwn ? 'sent' : 'received'}" data-message-id="${message.message_id}">
                <div class="message-bubble">
                    <div class="message-content">${this.escapeHtml(message.content)}</div>
                    <div class="message-time">${this.formatTime(message.created_at)}</div>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('afterbegin', messageHTML);
    }

    // ==========================================
    // USER FEATURES
    // ==========================================

    async blockUser(userId) {
        try {
            if (!confirm('Block this user?')) return;
            
            const response = await fetch(`/api/communication/user/${userId}/block`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            if (!response.ok) throw new Error('Block failed');
            
            const data = await response.json();
            
            if (data.action === 'blocked') {
                this.showNotification('User blocked');
            } else {
                this.showNotification('User unblocked');
            }
            
            return data;
        } catch (error) {
            console.error('Block error:', error);
            this.showError('Failed to block user');
            throw error;
        }
    }

    async updateConversationSettings(conversationId, settings) {
        try {
            const response = await fetch(`/api/communication/conversation/${conversationId}/settings`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(settings)
            });
            
            if (!response.ok) throw new Error('Settings update failed');
            
            const data = await response.json();
            this.showNotification('Settings updated');
            return data;
        } catch (error) {
            console.error('Settings error:', error);
            this.showError('Failed to update settings');
            throw error;
        }
    }

    // ==========================================
    // CALL HISTORY
    // ==========================================

    async loadCallHistory(page = 1) {
        try {
            const response = await fetch(`/api/communication/calls/history?page=${page}`, {
                headers: {'X-CSRFToken': this.getCSRFToken()}
            });
            
            if (!response.ok) throw new Error('Failed to load call history');
            
            const data = await response.json();
            this.displayCallHistory(data.calls);
        } catch (error) {
            console.error('Call history error:', error);
        }
    }

    displayCallHistory(calls) {
        const container = document.getElementById('call-history-list');
        if (!container) return;
        
        if (calls.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-3">No call history</p>';
            return;
        }
        
        const html = calls.map(call => `
            <div class="call-item p-2 border-bottom">
                <div class="d-flex align-items-center">
                    <i class="bi bi-${call.call_type === 'video' ? 'camera-video' : 'telephone'} 
                       text-${call.call_status === 'answered' ? 'success' : 'danger'} me-2"></i>
                    <div class="flex-grow-1">
                        <strong>${call.other_user.username}</strong>
                        <small class="d-block text-muted">
                            ${call.call_status} - ${this.formatDuration(call.duration_seconds)}
                        </small>
                    </div>
                    <small class="text-muted">${this.formatTimeAgo(call.started_at)}</small>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = html;
    }

    formatDuration(seconds) {
        if (!seconds) return '0s';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    }

    // ==========================================
    // SCREEN SHARING
    // ==========================================

    async startScreenShare() {
        try {
            const screenStream = await navigator.mediaDevices.getDisplayMedia({
                video: true,
                audio: false
            });
            
            const screenTrack = screenStream.getVideoTracks()[0];
            const sender = this.peerConnection.getSenders().find(s => s.track?.kind === 'video');
            
            if (sender) {
                sender.replaceTrack(screenTrack);
            }
            
            this.socket.emit('screen_share_start', {
                receiver_id: this.activeChatUserId,
                call_id: this.callId
            });
            
            screenTrack.onended = () => {
                this.stopScreenShare();
            };
            
            this.isScreenSharing = true;
            this.showNotification('Screen sharing started');
        } catch (error) {
            console.error('Screen share error:', error);
            this.showError('Failed to start screen sharing');
        }
    }

    async stopScreenShare() {
        if (!this.isScreenSharing) return;
        
        try {
            // Replace with camera track
            if (this.localStream) {
                const videoTrack = this.localStream.getVideoTracks()[0];
                const sender = this.peerConnection.getSenders().find(s => s.track?.kind === 'video');
                
                if (sender && videoTrack) {
                    await sender.replaceTrack(videoTrack);
                }
            }
            
            this.socket.emit('screen_share_stop', {
                receiver_id: this.activeChatUserId,
                call_id: this.callId
            });
            
            this.isScreenSharing = false;
            this.showNotification('Screen sharing stopped');
        } catch (error) {
            console.error('Stop screen share error:', error);
        }
    }

    handleScreenShareStarted(data) {
        this.showNotification('Screen sharing started');
    }

    handleScreenShareStopped(data) {
        this.showNotification('Screen sharing stopped');
    }

    // ==========================================
    // SOCKET.IO HANDLERS FOR NEW FEATURES
    // ==========================================

    handleMessageEdited(data) {
        const messageDiv = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageDiv) {
            const contentEl = messageDiv.querySelector('.message-content');
            if (contentEl) {
                contentEl.textContent = data.content;
            }
            
            const timeEl = messageDiv.querySelector('.message-time');
            if (timeEl && !timeEl.querySelector('.edited-indicator')) {
                timeEl.insertAdjacentHTML('beforeend', ' <span class="edited-indicator text-muted">(edited)</span>');
            }
        }
    }

    handleMessageDeleted(data) {
        const messageDiv = document.querySelector(`[data-message-id="${data.message_id}"]`);
        if (messageDiv) {
            const contentEl = messageDiv.querySelector('.message-content');
            if (contentEl) {
                contentEl.textContent = '[Message deleted]';
                contentEl.style.fontStyle = 'italic';
                contentEl.style.opacity = '0.6';
            }
        }
    }

    handleMessageReacted(data) {
        this.updateReactionsDisplay(data.message_id, data.reactions);
    }

    // ==========================================
    // UTILITY FUNCTIONS
    // ==========================================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTimeAgo(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diff = Math.floor((now - time) / 1000);
        
        if (diff < 60) return 'Just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        return time.toLocaleDateString();
    }
}

// Initialize communication system when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.communicationSystem = new CommunicationSystem();
});
