/**
 * FRONTEND INTEGRATION GUIDE
 * Complete examples for integrating all new communication features
 */

// ==========================================
// 1. FILE UPLOAD INTEGRATION
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
        return data; // Returns {file_url, file_name, file_size, message_type}
    } catch (error) {
        console.error('Upload error:', error);
        throw error;
    }
}

// Add to HTML (in communication_modal.html):
/*
<div class="message-input">
    <button class="btn btn-sm btn-outline-secondary" id="attach-file-btn" title="Attach file">
        <i class="bi bi-paperclip"></i>
    </button>
    <input type="file" id="file-input" style="display: none" accept="*/*">
    <input type="text" class="form-control" id="message-input" placeholder="Type a message...">
    <button class="btn btn-primary" id="send-message-btn">
        <i class="bi bi-send-fill"></i>
    </button>
</div>
*/

// Add event listener:
document.getElementById('attach-file-btn').addEventListener('click', () => {
    document.getElementById('file-input').click();
});

document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    try {
        this.showLoading('Uploading...');
        const uploadData = await this.uploadFile(file);
        
        // Send message with file
        await this.sendFileMessage(uploadData);
        
        this.hideLoading();
        e.target.value = ''; // Clear input
    } catch (error) {
        this.showError('Failed to upload file');
        this.hideLoading();
    }
});

async sendFileMessage(uploadData) {
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
    
    const data = await response.json();
    // Emit to Socket.IO...
}

// ==========================================
// 2. MESSAGE EDITING
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
        
        // Update UI
        const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (messageDiv) {
            messageDiv.querySelector('.message-content').textContent = newContent;
            // Add "edited" indicator
            const timeEl = messageDiv.querySelector('.message-time');
            if (!timeEl.querySelector('.edited-indicator')) {
                timeEl.insertAdjacentHTML('beforeend', ' <span class="edited-indicator">(edited)</span>');
            }
        }
        
        return await response.json();
    } catch (error) {
        console.error('Edit error:', error);
        throw error;
    }
}

// Add context menu to messages:
/*
<div class="message-actions dropdown" style="position: absolute; top: 5px; right: 5px;">
    <button class="btn btn-sm btn-link dropdown-toggle" data-bs-toggle="dropdown">
        <i class="bi bi-three-dots-vertical"></i>
    </button>
    <ul class="dropdown-menu">
        <li><a class="dropdown-item" onclick="editMessage('${msg.message_id}')">
            <i class="bi bi-pencil me-2"></i>Edit
        </a></li>
        <li><a class="dropdown-item" onclick="deleteMessage('${msg.message_id}')">
            <i class="bi bi-trash me-2"></i>Delete
        </a></li>
        <li><a class="dropdown-item" onclick="starMessage('${msg.message_id}')">
            <i class="bi bi-star me-2"></i>Star
        </a></li>
    </ul>
</div>
*/

// ==========================================
// 3. MESSAGE REACTIONS
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
    
    for (const [emoji, users] of Object.entries(reactions)) {
        if (users.length > 0) {
            const reactionBtn = document.createElement('button');
            reactionBtn.className = 'btn btn-sm btn-light me-1';
            reactionBtn.innerHTML = `${emoji} ${users.length}`;
            reactionBtn.onclick = () => this.reactToMessage(messageId, emoji);
            reactionsEl.appendChild(reactionBtn);
        }
    }
}

// Add emoji picker (in HTML):
/*
<div class="emoji-picker" style="display: none; position: absolute; bottom: 100%; background: white; 
     border: 1px solid #ddd; border-radius: 8px; padding: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
    <button onclick="reactToMessage(currentMessageId, '👍')">👍</button>
    <button onclick="reactToMessage(currentMessageId, '❤️')">❤️</button>
    <button onclick="reactToMessage(currentMessageId, '😂')">😂</button>
    <button onclick="reactToMessage(currentMessageId, '😮')">😮</button>
    <button onclick="reactToMessage(currentMessageId, '😢')">😢</button>
    <button onclick="reactToMessage(currentMessageId, '🙏')">🙏</button>
</div>
*/

// ==========================================
// 4. GROUP CHATS
// ==========================================

async loadGroups() {
    try {
        const response = await fetch('/api/communication/groups', {
            headers: {'X-CSRFToken': this.getCSRFToken()}
        });
        const data = await response.json();
        this.displayGroups(data.groups);
    } catch (error) {
        console.error('Error loading groups:', error);
    }
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
        
        const data = await response.json();
        
        // Join group room
        this.socket.emit('join_group', {group_id: data.group.group_id});
        
        return data.group;
    } catch (error) {
        console.error('Error creating group:', error);
        throw error;
    }
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
        
        return await response.json();
    } catch (error) {
        console.error('Error sending group message:', error);
        throw error;
    }
}

// Socket.IO handler for group messages
this.socket.on('group_message', (data) => {
    console.log('Group message received:', data);
    // Display in group chat UI
    this.appendGroupMessage(data);
});

// ==========================================
// 5. SEARCH FUNCTIONALITY
// ==========================================

async searchMessages(query) {
    try {
        const response = await fetch(`/api/communication/search?q=${encodeURIComponent(query)}`, {
            headers: {'X-CSRFToken': this.getCSRFToken()}
        });
        const data = await response.json();
        this.displaySearchResults(data.messages);
    } catch (error) {
        console.error('Search error:', error);
    }
}

// Add search to HTML:
/*
<div class="search-panel" style="display: none;">
    <input type="text" class="form-control" id="message-search" 
           placeholder="Search messages..." onkeyup="searchMessages(this.value)">
    <div id="search-results" class="mt-2"></div>
</div>
*/

// ==========================================
// 6. PAGINATION
// ==========================================

async loadMoreMessages(beforeMessageId) {
    try {
        const response = await fetch(
            `/api/communication/conversation/${this.activeChatUserId}/paginated?before_id=${beforeMessageId}&per_page=50`,
            {headers: {'X-CSRFToken': this.getCSRFToken()}}
        );
        const data = await response.json();
        
        // Prepend older messages
        data.messages.forEach(msg => this.prependMessage(msg));
        
        return data.has_more;
    } catch (error) {
        console.error('Pagination error:', error);
    }
}

// Add scroll handler:
const messagesContainer = document.getElementById('messages-container');
messagesContainer.addEventListener('scroll', () => {
    if (messagesContainer.scrollTop === 0 && !this.loadingMore) {
        // Load more messages
        const firstMessage = messagesContainer.querySelector('.message');
        if (firstMessage) {
            const messageId = firstMessage.dataset.messageId;
            this.loadingMore = true;
            this.loadMoreMessages(messageId).then(() => {
                this.loadingMore = false;
            });
        }
    }
});

// ==========================================
// 7. BLOCK USER
// ==========================================

async blockUser(userId) {
    try {
        const response = await fetch(`/api/communication/user/${userId}/block`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            }
        });
        
        const data = await response.json();
        
        if (data.action === 'blocked') {
            this.showNotification('User blocked');
        } else {
            this.showNotification('User unblocked');
        }
        
        return data;
    } catch (error) {
        console.error('Block error:', error);
        throw error;
    }
}

// ==========================================
// 8. CONVERSATION SETTINGS
// ==========================================

async updateConversationSettings(conversationId, settings) {
    try {
        const response = await fetch(`/api/communication/conversation/${conversationId}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify(settings) // {is_muted: true, is_archived: false, is_pinned: true}
        });
        
        return await response.json();
    } catch (error) {
        console.error('Settings error:', error);
        throw error;
    }
}

// ==========================================
// 9. CALL HISTORY
// ==========================================

async loadCallHistory(page = 1) {
    try {
        const response = await fetch(`/api/communication/calls/history?page=${page}`, {
            headers: {'X-CSRFToken': this.getCSRFToken()}
        });
        const data = await response.json();
        this.displayCallHistory(data.calls);
    } catch (error) {
        console.error('Call history error:', error);
    }
}

displayCallHistory(calls) {
    const html = calls.map(call => `
        <div class="call-item p-2 border-bottom">
            <div class="d-flex align-items-center">
                <i class="bi bi-${call.call_type === 'video' ? 'camera-video' : 'telephone'} 
                   text-${call.is_outgoing ? 'success' : 'primary'} me-2"></i>
                <div class="flex-grow-1">
                    <strong>${call.other_user.username}</strong>
                    <small class="d-block text-muted">
                        ${call.is_outgoing ? 'Outgoing' : 'Incoming'} 
                        ${call.call_status} - ${this.formatDuration(call.duration_seconds)}
                    </small>
                </div>
                <small class="text-muted">${this.formatTimeAgo(call.started_at)}</small>
            </div>
        </div>
    `).join('');
    
    document.getElementById('call-history-list').innerHTML = html;
}

// ==========================================
// 10. SCREEN SHARING
// ==========================================

async startScreenShare() {
    try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: false
        });
        
        // Replace video track with screen track
        const screenTrack = screenStream.getVideoTracks()[0];
        const sender = this.peerConnection.getSenders().find(s => s.track?.kind === 'video');
        
        if (sender) {
            sender.replaceTrack(screenTrack);
        }
        
        // Notify other user
        this.socket.emit('screen_share_start', {
            receiver_id: this.activeChatUserId,
            call_id: this.callId
        });
        
        // Stop screen sharing when user closes sharing
        screenTrack.onended = () => {
            this.stopScreenShare();
        };
        
        this.isScreenSharing = true;
    } catch (error) {
        console.error('Screen share error:', error);
        this.showError('Failed to start screen sharing');
    }
}

// Add to Socket.IO handlers:
this.socket.on('screen_share_started', (data) => {
    this.showNotification('Screen sharing started');
});

// ==========================================
// COMPLETE EXAMPLE USAGE
// ==========================================

// Initialize system
const comm = new CommunicationSystem();

// Send a message
await comm.sendMessage();

// Upload and send file
const fileData = await comm.uploadFile(file);
await comm.sendFileMessage(fileData);

// Edit message
await comm.editMessage('msg-id-123', 'New content');

// React to message
await comm.reactToMessage('msg-id-123', '👍');

// Create group
const group = await comm.createGroup('Team Chat', 'Project discussion', [2, 3, 4]);

// Send group message
await comm.sendGroupMessage(group.group_id, 'Hello team!');

// Search messages
await comm.searchMessages('important');

// Block user
await comm.blockUser(5);

// Mute conversation
await comm.updateConversationSettings(conv_id, {is_muted: true});

// Start screen share
await comm.startScreenShare();
