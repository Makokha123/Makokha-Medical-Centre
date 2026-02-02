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
