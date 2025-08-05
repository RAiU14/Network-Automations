// DOM elements
const fileDropArea = document.getElementById('fileDropArea');
const fileInput = document.getElementById('fileInput');
const fileText = document.getElementById('fileText');
const fileName = document.getElementById('fileName');
const ticketInput = document.getElementById('ticket');
const ticketError = document.getElementById('ticketError');

// Auto-hide flash messages after 8 seconds
document.addEventListener('DOMContentLoaded', function() {
  const flashMessages = document.querySelectorAll('.flash');
  flashMessages.forEach(function(message, index) {
    setTimeout(function() {
      if (message.parentNode) {
        message.classList.add('fade-out');
        setTimeout(function() {
          if (message.parentNode) {
            message.remove();
          }
        }, 1000); // Wait for fade-out animation
      }
    }, 8000); // Auto-hide after 8 seconds
  });
});

// Manual close flash message
function closeFlashMessage(messageId) {
  const message = document.getElementById(messageId);
  if (message) {
    message.classList.add('fade-out');
    setTimeout(function() {
      if (message.parentNode) {
        message.remove();
      }
    }, 1000);
  }
}

// Function to update UI when file is selected
function updateFileDisplay(file) {
  if (file && file.name.endsWith('.zip')) {
    fileDropArea.classList.add('file-selected');
    fileText.style.display = 'none';
    fileName.textContent = `Selected: ${file.name}`;
    fileName.style.display = 'block';
  } else {
    resetFileDisplay();
    if (file && !file.name.endsWith('.zip')) {
      alert('Only zip files are allowed.');
    }
  }
}

// Function to reset file display
function resetFileDisplay() {
  fileDropArea.classList.remove('file-selected');
  fileText.style.display = 'block';
  fileName.style.display = 'none';
  fileInput.value = '';
}

// Function for ticket number validation
function validateTicketNumber(ticketNumber) {
  const pattern = /^SVR\d+$/;
  return pattern.test(ticketNumber);
}

// Ticket input validation
ticketInput.addEventListener('input', function() {
  const ticketValue = this.value.trim();
  if (ticketValue && !validateTicketNumber(ticketValue)) {
    ticketError.style.display = 'block';
    this.style.borderColor = 'red';
  } else {
    ticketError.style.display = 'none';
    this.style.borderColor = '#aaa';
  }
});

// Click to browse
fileDropArea.addEventListener('click', () => fileInput.click());

// File input change
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    updateFileDisplay(e.target.files[0]);
  }
});

// Drag and drop events
fileDropArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  fileDropArea.classList.add('dragover');
});

fileDropArea.addEventListener('dragleave', (e) => {
  e.preventDefault();
  fileDropArea.classList.remove('dragover');
});

fileDropArea.addEventListener('drop', (e) => {
  e.preventDefault();
  fileDropArea.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) {
    const file = e.dataTransfer.files[0];
    if (file.name.endsWith('.zip')) {
      fileInput.files = e.dataTransfer.files;
      updateFileDisplay(file);
    } else {
      alert('Only zip files are allowed.');
    }
  }
});

// Enhanced reset button functionality
document.querySelector('button[type="reset"]').addEventListener('click', (e) => {
  e.preventDefault();
  document.getElementById('uploadForm').reset();
  resetFileDisplay();
  
  // Clear any flash messages
  const flashMessages = document.querySelectorAll('.flash');
  flashMessages.forEach(function(message) {
    message.classList.add('fade-out');
    setTimeout(function() {
      if (message.parentNode) {
        message.remove();
      }
    }, 1000);
  });
  
  // Remove loading message if exists
  const loadingMessage = document.getElementById('loading-message');
  if (loadingMessage) {
    loadingMessage.remove();
  }
});

// Form submission with loading feedback
document.getElementById('uploadForm').addEventListener('submit', function(e) {
  const ticketValue = ticketInput.value.trim();
  
  // Validation
  if (!ticketValue) {
    e.preventDefault();
    alert('Ticket number is required.');
    return;
  }
  
  if (!validateTicketNumber(ticketValue)) {
    e.preventDefault();
    alert('Ticket number must start with "SVR" followed by numbers (e.g., SVR137572722)');
    return;
  }
  
  if (!fileInput.files.length) {
    e.preventDefault();
    alert('Please upload a zip file.');
    return;
  }
  
  // Show loading feedback immediately
  const submitBtn = this.querySelector('.submit');
  const originalText = submitBtn.textContent;
  
  submitBtn.disabled = true;
  submitBtn.textContent = 'Uploading...';
  
  // Create loading message
  let loadingMessage = document.getElementById('loading-message');
  if (!loadingMessage) {
    loadingMessage = document.createElement('div');
    loadingMessage.id = 'loading-message';
    loadingMessage.className = 'loading-message';
    loadingMessage.textContent = '⏳ Uploading file... Processing will start in background!';
    
    // Insert after form
    this.parentNode.insertBefore(loadingMessage, this.nextSibling);
  }
  
  // Re-enable button after page reload (handled by browser)
  // The Flask redirect will cause page reload, clearing the disabled state
});

// Download functionality
function checkAndDownload() {
  const ticketInput = document.getElementById('download-ticket');
  const ticket = ticketInput.value.trim();
  const statusDiv = document.getElementById('download-status');
  
  if (!ticket) {
    statusDiv.innerHTML = '<div class="status-indicator status-not-ready">Please enter a ticket number</div>';
    return;
  }
  
  if (!validateTicketNumber(ticket)) {
    statusDiv.innerHTML = '<div class="status-indicator status-not-ready">Invalid ticket number format</div>';
    return;
  }
  
  // Show checking status
  statusDiv.innerHTML = '<div class="status-indicator status-checking">Checking status...</div>';
  
  // Check status via AJAX
  fetch(`/check_status/${ticket}`)
    .then(response => response.json())
    .then(data => {
      if (data.download_ready) {
        statusDiv.innerHTML = '<div class="status-indicator status-ready">✅ Report ready for download</div>';
        // Trigger download
        window.location.href = `/download/${ticket}`;
      } else if (data.uploaded) {
        statusDiv.innerHTML = '<div class="status-indicator status-not-ready">⏳ Processing not complete yet. Try again in a few minutes.</div>';
      } else {
        statusDiv.innerHTML = '<div class="status-indicator status-not-ready">❌ Ticket not found</div>';
      }
    })
    .catch(error => {
      console.error('Error checking status:', error);
      statusDiv.innerHTML = '<div class="status-indicator status-not-ready">❌ Error checking status</div>';
    });
}

// Enter key support for download
document.getElementById('download-ticket').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') {
    checkAndDownload();
  }
});
