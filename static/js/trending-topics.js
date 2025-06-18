// Debug logging
console.log('Trending topics script loaded');

// Initialize toast
const refreshToast = new bootstrap.Toast(document.getElementById('refresh-toast'));

// Get refresh button and add click handler
const refreshButton = document.getElementById('refresh-topics');
console.log('Refresh button:', refreshButton);

if (refreshButton) {
    refreshButton.addEventListener('click', async function() {
        console.log('Refresh button clicked');
        const button = this;
        const spinner = document.getElementById('refresh-spinner');
        const text = document.getElementById('refresh-text');
        
        try {
            // Show loading state
            button.disabled = true;
            spinner.classList.remove('d-none');
            text.textContent = 'Refreshing...';
            refreshToast.show();
            
            console.log('Sending refresh request...');
            const response = await fetch('/api/refresh-topics', { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            console.log('Response received:', response);
            
            const data = await response.json();
            console.log('Response data:', data);
            
            if (response.ok) {
                // Update toast message
                document.querySelector('#refresh-toast .toast-body').textContent = 
                    `Successfully fetched ${data.count} new topics!`;
                
                // Reload page after a short delay
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                throw new Error(data.error || 'Error refreshing topics');
            }
        } catch (error) {
            console.error('Error:', error);
            document.querySelector('#refresh-toast .toast-body').textContent = 
                `Error: ${error.message}`;
        } finally {
            // Reset button state
            button.disabled = false;
            spinner.classList.add('d-none');
            text.textContent = 'Refresh Topics';
        }
    });
} else {
    console.error('Refresh button not found!');
}

// Initialize topic selection
const topicModal = new bootstrap.Modal(document.getElementById('topicModal'));
let currentTopicId = null;

// Add click handlers to topic selection buttons
document.querySelectorAll('.select-topic').forEach(button => {
    button.addEventListener('click', function() {
        const topicId = this.dataset.topicId;
        const topicTitle = this.dataset.topicTitle;
        const topicDescription = this.dataset.topicDescription;
        
        currentTopicId = topicId;
        document.getElementById('article-form').dataset.topicId = topicId;
        topicModal.show();
    });
});

// Add submit handler for article creation
document.getElementById('submit-article').addEventListener('click', async function() {
    if (!currentTopicId) return;
    
    const form = document.getElementById('article-form');
    const formData = new FormData(form);
    formData.append('topic_id', currentTopicId);
    
    try {
        const response = await fetch('/api/create-article', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            window.location.href = `/prompts`;
        } else {
            const data = await response.json();
            throw new Error(data.error || 'Error creating article');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating article: ' + error.message);
    }
    
    topicModal.hide();
}); 