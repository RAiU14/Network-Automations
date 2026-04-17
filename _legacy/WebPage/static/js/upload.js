// DOM elements
const fileDropArea = document.getElementById('fileDropArea');
const fileInput = document.getElementById('fileInput');
const fileText = document.getElementById('fileText');
const fileName = document.getElementById('fileName');
const ticketInput = document.getElementById('ticket');
const ticketError = document.getElementById('ticketError');
const uploadForm = document.getElementById('uploadForm');
const overwriteModal = document.getElementById('overwriteModal');

// State for concurrent uploads - NON-BLOCKING
let activeUploads = new Set(); // Just track ticket numbers
let pendingOverwrites = new Map(); // Store pending overwrite data

// Debug function
function debugLog(message, data = null) {
  console.log(`[UPLOAD] ${message}`, data || '');
}

// Quick validation function
function validateTicketNumber(ticketNumber) {
  const pattern = /^SVR\d+$/;
  return pattern.test(ticketNumber);
}

// Fast client-side validation
function validateForm() {
  const ticket = ticketInput.value.trim();
  const technology = document.getElementById('technology').value;
  const file = fileInput.files[0];
  
  if (!ticket) {
    showAlert('Ticket number is required', 'error');
    return false;
  }
  
  if (!validateTicketNumber(ticket)) {
    showAlert('Invalid ticket number format', 'error');
    return false;
  }
  
  if (!technology) {
    showAlert('Please select a technology', 'error');
    return false;
  }
  
  if (!file) {
    showAlert('Please select a zip file', 'error');
    return false;
  }
  
  if (!file.name.endsWith('.zip')) {
    showAlert('Only zip files are allowed', 'error');
    return false;
  }
  
  return true;
}

// Show alerts
function showAlert(message, type = 'info') {
  debugLog(`Alert: ${type} - ${message}`);
  
  // Create alert element
  const alertDiv = document.createElement('div');
  alertDiv.className = `flash ${type}`;
  alertDiv.innerHTML = `
    ${message}
    <button class="close-btn" onclick="this.parentElement.remove()">&times;</button>
  `;
  
  const container = document.querySelector('.container');
  container.insertBefore(alertDiv, container.firstChild);
  
  // Auto-remove after 4 seconds
  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.classList.add('fade-out');
      setTimeout(() => {
        if (alertDiv.parentNode) {
          alertDiv.remove();
        }
      }, 500);
    }
  }, 4000);
}

// Update file display
function updateFileDisplay(file) {
  if (file && file.name.endsWith('.zip')) {
    fileDropArea.classList.add('file-selected');
    fileText.style.display = 'none';
    
    const fileNameText = document.getElementById('fileNameText');
    const fileSizeText = document.getElementById('fileSizeText');
    
    if (fileNameText) {
      fileNameText.textContent = file.name;
    } else {
      fileName.textContent = `Selected: ${file.name}`;
    }
    
    if (fileSizeText) {
      const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
      fileSizeText.textContent = `Size: ${sizeInMB} MB`;
    }
    
    fileName.style.display = 'block';
  } else {
    resetFileDisplay();
  }
}

// Reset file display
function resetFileDisplay() {
  fileDropArea.classList.remove('file-selected');
  fileText.style.display = 'block';
  fileName.style.display = 'none';
  fileInput.value = '';
}

// NON-BLOCKING duplicate check
function checkForDuplicateAsync(ticket) {
  debugLog('Starting async duplicate check', ticket);
  
  // Fire and forget - don't wait for response
  fetch('/api/check_ticket', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ticket: ticket })
  })
  .then(response => response.json())
  .then(result => {
    if (result.success && result.exists) {
      debugLog('Duplicate found, showing modal', ticket);
      showDuplicateModal(ticket, result);
    } else {
      debugLog('No duplicate found', ticket);
    }
  })
  .catch(error => {
    debugLog('Duplicate check error (ignoring)', error.message);
    // Ignore errors in duplicate check - don't block upload
  });
}

// Show duplicate modal
function showDuplicateModal(ticket, ticketData) {
  const modal = document.getElementById('overwriteModal');
  const ticketNumber = document.getElementById('existingTicketNumber');
  const ticketInfo = document.getElementById('existingTicketInfo');
  
  if (!modal || !ticketNumber || !ticketInfo) {
    debugLog('Modal elements not found');
    return;
  }
  
  ticketNumber.textContent = ticket;
  
  // Build info display
  let infoHtml = '<div style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 4px; font-size: 0.9rem;">';
  
  if (ticketData.details && ticketData.details.metadata) {
    infoHtml += `
      <strong>Existing Data:</strong><br>
      📅 Last uploaded: ${ticketData.details.metadata.timestamp || 'Unknown'}<br>
      🔧 Technology: ${ticketData.details.metadata.technology || 'Unknown'}<br>
    `;
    if (ticketData.details.metadata.comment) {
      infoHtml += `💬 Comment: ${ticketData.details.metadata.comment}<br>`;
    }
  }
  
  infoHtml += '</div>';
  ticketInfo.innerHTML = infoHtml;
  
  modal.style.display = 'block';
  
  // Store pending data if user wants to overwrite later
  const formData = pendingOverwrites.get(ticket);
  if (!formData) {
    debugLog('No pending overwrite data found for', ticket);
  }
}

// Close overwrite modal
function closeOverwriteModal() {
  const modal = document.getElementById('overwriteModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

// Confirm overwrite
function confirmOverwrite() {
  const ticketNumber = document.getElementById('existingTicketNumber').textContent;
  const formData = pendingOverwrites.get(ticketNumber);
  
  if (!formData) {
    showAlert('No pending data found. Please upload again.', 'error');
    closeOverwriteModal();
    return;
  }
  
  // Add overwrite flag and submit
  formData.append('overwrite_confirmed', 'true');
  submitUploadDirectly(formData, ticketNumber);
  
  // Clean up
  pendingOverwrites.delete(ticketNumber);
  closeOverwriteModal();
}

// DIRECT UPLOAD - Fire and forget
function submitUploadDirectly(formData, ticket) {
  debugLog('Submitting upload directly', ticket);
  
  // Show immediate feedback
  showAlert(`Upload started for ticket ${ticket}`, 'success');
  
  // Fire and forget upload - don't wait for response
  fetch('/upload', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(result => {
    if (result.success) {
      showAlert(`Upload completed successfully for ${ticket}`, 'success');
    } else {
      showAlert(`Upload failed for ${ticket}: ${result.error}`, 'error');
    }
  })
  .catch(error => {
    showAlert(`Upload error for ${ticket}: ${error.message}`, 'error');
  })
  .finally(() => {
    // Remove from active uploads
    activeUploads.delete(ticket);
    debugLog('Upload process completed for', ticket);
  });
}

// MAIN FORM SUBMISSION - COMPLETELY NON-BLOCKING
if (uploadForm) {
  uploadForm.addEventListener('submit', function(e) {
    e.preventDefault();
    debugLog('Form submission started - non-blocking mode');
    
    // Validate form
    if (!validateForm()) {
      return;
    }
    
    const ticket = ticketInput.value.trim();
    const technology = document.getElementById('technology').value;
    const comment = document.getElementById('comment').value.trim();
    const file = fileInput.files[0];
    
    // Check if already uploading this ticket
    if (activeUploads.has(ticket)) {
      showAlert(`Upload already in progress for ${ticket}`, 'warning');
      return;
    }
    
    // Add to active uploads
    activeUploads.add(ticket);
    debugLog('Added to active uploads', ticket);
    
    // Create form data
    const formData = new FormData();
    formData.append('ticket', ticket);
    formData.append('comment', comment);
    formData.append('technology', technology);
    formData.append('file', file);
    
    // Store for potential overwrite
    pendingOverwrites.set(ticket, formData);
    
    // IMMEDIATE FORM RESET - Don't wait for anything
    uploadForm.reset();
    resetFileDisplay();
    clearValidationErrors();
    
    debugLog('Form reset completed immediately');
    
    // Start upload process (fire and forget)
    submitUploadDirectly(formData, ticket);
    
    // Start duplicate check in parallel (optional - doesn't block)
    checkForDuplicateAsync(ticket);
    
    // Show success message immediately
    showAlert(`Upload initiated for ${ticket}. You can upload another file now.`, 'info');
  });
}

// Clear validation errors
function clearValidationErrors() {
  if (ticketError) {
    ticketError.style.display = 'none';
  }
  if (ticketInput) {
    ticketInput.style.borderColor = '#aaa';
  }
}

// File input handling
if (fileInput) {
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      updateFileDisplay(e.target.files[0]);
    }
  });
}

// Drag and drop
if (fileDropArea) {
  fileDropArea.addEventListener('click', () => fileInput.click());
  
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
        showAlert('Only zip files are allowed', 'error');
      }
    }
  });
}

// Ticket validation
if (ticketInput) {
  ticketInput.addEventListener('input', function() {
    const ticketValue = this.value.trim();
    if (ticketValue && !validateTicketNumber(ticketValue)) {
      if (ticketError) {
        ticketError.style.display = 'block';
      }
      this.style.borderColor = 'red';
    } else {
      if (ticketError) {
        ticketError.style.display = 'none';
      }
      this.style.borderColor = '#aaa';
    }
  });
}

// Reset button
const resetBtn = document.querySelector('button[type="reset"]');
if (resetBtn) {
  resetBtn.addEventListener('click', (e) => {
    e.preventDefault();
    uploadForm.reset();
    resetFileDisplay();
    clearValidationErrors();
    debugLog('Manual form reset');
  });
}

// Download functionality
function checkAndDownload() {
  const ticketInputDownload = document.getElementById('download-ticket');
  const ticket = ticketInputDownload.value.trim();
  const statusDiv = document.getElementById('download-status');
  
  if (!ticket) {
    statusDiv.innerHTML = '<div class="status-indicator status-not-ready">Please enter a ticket number</div>';
    return;
  }
  
  if (!validateTicketNumber(ticket)) {
    statusDiv.innerHTML = '<div class="status-indicator status-not-ready">Invalid ticket number format</div>';
    return;
  }
  
  statusDiv.innerHTML = '<div class="status-indicator status-checking">Checking status...</div>';
  
  fetch(`/check_status/${ticket}`)
    .then(response => response.json())
    .then(data => {
      if (data.download_ready) {
        statusDiv.innerHTML = '<div class="status-indicator status-ready">✅ Report ready for download</div>';
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

// Modal event handlers
window.addEventListener('click', function(event) {
  if (event.target === overwriteModal) {
    closeOverwriteModal();
  }
});

document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape' && overwriteModal && overwriteModal.style.display === 'block') {
    closeOverwriteModal();
  }
});

// Initialize
document.addEventListener('DOMContentLoaded', function() {
  debugLog('Non-blocking upload system initialized');
  console.log('✅ Ready for concurrent uploads - form resets immediately after each submission');
});
