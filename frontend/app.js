// Use relative path or current origin for API
const API_URL = window.location.origin + '/api';

let selectedFile = null;
let currentJobId = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeUploadZone();
    initializeFormatSelection();
    initializeConvertButton();
});

// Upload Zone Functionality
function initializeUploadZone() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const fileInfo = document.getElementById('fileInfo');
    const removeFileBtn = document.getElementById('removeFile');

    // Click to browse
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });

    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    // File selection
    fileInput.addEventListener('change', (e) => {
        handleFileSelect(e.target.files[0]);
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');

        const file = e.dataTransfer.files[0];
        handleFileSelect(file);
    });

    // Remove file
    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });
}

function handleFileSelect(file) {
    if (!file) return;

    // Validate file type
    if (file.type !== 'application/pdf') {
        showError('Invalid file type. Please upload a PDF file.');
        return;
    }

    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        showError('File too large. Maximum file size is 10MB.');
        return;
    }

    selectedFile = file;
    showFileInfo(file);
    hideError();
}

function showFileInfo(file) {
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');

    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);

    fileInfo.classList.add('show');
}

function clearFile() {
    selectedFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('fileInfo').classList.remove('show');
    hideResults();
    hideError();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Format Selection
function initializeFormatSelection() {
    const radioButtons = document.querySelectorAll('input[name="output_format"]');
    radioButtons.forEach(radio => {
        radio.addEventListener('change', () => {
            hideResults();
            hideError();
        });
    });
}

// Convert Button
function initializeConvertButton() {
    const convertBtn = document.getElementById('convertBtn');
    convertBtn.addEventListener('click', handleConvert);
}

async function handleConvert() {
    if (!selectedFile) {
        showError('Please select a PDF file first.');
        return;
    }

    const outputFormat = document.querySelector('input[name="output_format"]:checked').value;

    // Disable button and show progress
    const convertBtn = document.getElementById('convertBtn');
    convertBtn.disabled = true;
    convertBtn.innerHTML = '<span class="spinner"></span> Processing...';

    showProgress('Uploading and processing PDF...');
    hideResults();
    hideError();

    // Create form data
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('output_format', outputFormat);

    try {
        // Upload and convert
        const response = await fetch(`${API_URL}/convert`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Conversion failed');
        }

        currentJobId = data.job_id;

        // Update progress
        updateProgress(80, 'Finalizing...');

        // Show results
        await new Promise(resolve => setTimeout(resolve, 500));
        updateProgress(100, 'Complete!');

        showResults(data);

    } catch (error) {
        console.error('Conversion error:', error);
        showError(error.message || 'Failed to convert PDF. Please try again.');
    } finally {
        // Re-enable button
        hideProgress();
        convertBtn.disabled = false;
        convertBtn.innerHTML = 'Convert to Spreadsheet';
    }
}

// Progress
function showProgress(message) {
    const progressSection = document.getElementById('progressSection');
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');

    progressText.textContent = message;
    progressBar.style.width = '30%';
    progressSection.classList.add('show');
}

function updateProgress(percent, message) {
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');

    progressBar.style.width = percent + '%';
    if (message) {
        progressText.textContent = message;
    }
}

function hideProgress() {
    const progressSection = document.getElementById('progressSection');
    progressSection.classList.remove('show');
}

// Results
function showResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const transactionCount = document.getElementById('transactionCount');
    const dateRange = document.getElementById('dateRange');
    const totalDebits = document.getElementById('totalDebits');
    const totalCredits = document.getElementById('totalCredits');
    const downloadSection = document.getElementById('downloadSection');

    // Show transaction count
    transactionCount.textContent = data.transaction_count || 0;

    // Show summary stats
    if (data.summary) {
        dateRange.textContent = data.summary.date_range || 'N/A';
        totalDebits.textContent = 'R ' + (data.summary.total_debits || '0.00');
        totalCredits.textContent = 'R ' + (data.summary.total_credits || '0.00');
    }

    // Clear download section
    downloadSection.innerHTML = '';

    // Show appropriate download/link button
    if (data.output_format === 'excel') {
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'download-btn';
        downloadBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20">
                <path fill="currentColor" d="M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z"/>
            </svg>
            Download Excel File
        `;
        downloadBtn.addEventListener('click', () => downloadFile(data.job_id));
        downloadSection.appendChild(downloadBtn);

        if (data.warning) {
            const warningText = document.createElement('p');
            warningText.style.color = 'rgba(255,255,255,0.9)';
            warningText.style.fontSize = '0.9rem';
            warningText.style.marginTop = '10px';
            warningText.textContent = '⚠️ ' + data.warning;
            downloadSection.appendChild(warningText);
        }
    } else if (data.output_format === 'google_sheets') {
        const sheetBtn = document.createElement('a');
        sheetBtn.href = data.sheet_url;
        sheetBtn.target = '_blank';
        sheetBtn.className = 'sheet-link-btn';
        sheetBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20">
                <path fill="currentColor" d="M19,3H5C3.9,3 3,3.9 3,5V19C3,20.1 3.9,21 5,21H19C20.1,21 21,20.1 21,19V5C21,3.9 20.1,3 19,3M9,17H7V15H9V17M9,13H7V11H9V13M9,9H7V7H9V9M13,17H11V15H13V17M13,13H11V11H13V13M13,9H11V7H13V9M17,17H15V15H17V17M17,13H15V11H17V13M17,9H15V7H17V9Z"/>
            </svg>
            Open Google Sheet
        `;
        downloadSection.appendChild(sheetBtn);
    }

    // Add new conversion button
    const newConversionBtn = document.createElement('button');
    newConversionBtn.className = 'new-conversion-btn';
    newConversionBtn.innerHTML = 'Convert Another File';
    newConversionBtn.addEventListener('click', resetApp);
    downloadSection.appendChild(newConversionBtn);

    resultsSection.classList.add('show');
}

function hideResults() {
    const resultsSection = document.getElementById('resultsSection');
    resultsSection.classList.remove('show');
}

async function downloadFile(jobId) {
    try {
        const downloadUrl = `${API_URL}/download/${jobId}`;

        // Trigger download
        window.location.href = downloadUrl;

        // Clean up files after a short delay
        setTimeout(async () => {
            try {
                await fetch(`${API_URL}/cleanup/${jobId}`, { method: 'POST' });
            } catch (error) {
                console.error('Cleanup error:', error);
            }
        }, 2000);

    } catch (error) {
        console.error('Download error:', error);
        showError('Failed to download file. Please try again.');
    }
}

// Error Handling
function showError(message) {
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');

    errorMessage.textContent = message;
    errorSection.classList.add('show');
}

function hideError() {
    const errorSection = document.getElementById('errorSection');
    errorSection.classList.remove('show');
}

// Reset App
function resetApp() {
    clearFile();
    hideResults();
    hideError();
    hideProgress();
    currentJobId = null;

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Try Again Button
document.addEventListener('DOMContentLoaded', () => {
    const tryAgainBtn = document.getElementById('tryAgainBtn');
    if (tryAgainBtn) {
        tryAgainBtn.addEventListener('click', () => {
            hideError();
        });
    }
});
