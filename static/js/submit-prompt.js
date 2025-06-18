// Debug logging
console.log('Submit prompt script loaded');

// Initialize toast
const submitToast = new bootstrap.Toast(document.getElementById('submit-toast'));

// Get form and add submit handler
const form = document.getElementById('submit-prompt-form');
const submitButton = document.getElementById('submit-button');
const spinner = document.getElementById('submit-spinner');

if (form) {
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        console.log('Form submitted');
        
        try {
            // Show loading state
            submitButton.disabled = true;
            spinner.classList.remove('d-none');
            submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';
            submitToast.show();
            
            // Get form data
            const formData = new FormData(form);
            
            console.log('Sending submit request...');
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData
            });
            console.log('Response received:', response);
            
            if (response.ok) {
                // Update toast message
                document.querySelector('#submit-toast .toast-body').textContent = 
                    'Prompt submitted successfully! Redirecting to prompts page...';
                
                // Redirect after a short delay
                setTimeout(() => {
                    window.location.href = '/prompts';
                }, 1500);
            } else {
                const data = await response.json();
                throw new Error(data.error || 'Error submitting prompt');
            }
        } catch (error) {
            console.error('Error:', error);
            document.querySelector('#submit-toast .toast-body').textContent = 
                `Error: ${error.message}`;
            
            // Reset button state
            submitButton.disabled = false;
            spinner.classList.add('d-none');
            submitButton.innerHTML = 'Submit Prompt';
        }
    });
} else {
    console.error('Submit form not found!');
} 