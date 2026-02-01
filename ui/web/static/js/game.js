/**
 * EU4 Strategy Game Web UI - JavaScript
 */

// Global state
let currentProvinceId = null;
let currentView = 'province-list';

/**
 * Toggle province card expand/collapse
 */
function toggleProvince(provinceId) {
    const body = document.getElementById(`province-body-${provinceId}`);
    const icon = document.getElementById(`toggle-${provinceId}`);
    
    if (body.style.display === 'none') {
        body.style.display = 'block';
        icon.textContent = '▲';
    } else {
        body.style.display = 'none';
        icon.textContent = '▼';
    }
}

/**
 * Show project modal for a province
 */
function showProjectModal(provinceId) {
    currentProvinceId = provinceId;
    
    // Get province name
    const provinceCard = document.querySelector(`[data-province-id="${provinceId}"]`);
    const provinceName = provinceCard.querySelector('.province-name').textContent;
    
    document.getElementById('project-province-name').textContent = provinceName;
    
    // Get current treasury
    const treasuryElement = document.querySelector('.treasury .gold');
    document.getElementById('project-treasury').textContent = treasuryElement.textContent;
    
    // Reset selection
    const radios = document.querySelectorAll('input[name="project-type"]');
    radios.forEach(radio => radio.checked = false);
    
    // Show modal
    document.getElementById('project-modal').style.display = 'flex';
}

/**
 * Close a modal
 */
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
    currentProvinceId = null;
}

/**
 * Submit project initiation
 */
async function submitProject() {
    const selectedType = document.querySelector('input[name="project-type"]:checked');
    
    if (!selectedType) {
        alert('Please select a project type');
        return;
    }
    
    if (!currentProvinceId) {
        return;
    }
    
    try {
        const response = await fetch(`/api/provinces/${currentProvinceId}/projects`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                project_type: selectedType.value
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert('Project initiated successfully!');
            closeModal('project-modal');
            // Refresh page to show updated state
            window.location.reload();
        } else {
            alert(result.detail || 'Failed to initiate project');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while initiating the project');
    }
}

/**
 * Show province events (placeholder)
 */
function showProvinceEvents(provinceId) {
    // Will be implemented in Phase 3.2
    alert('Event view not yet implemented');
}

/**
 * Show transfer modal (placeholder)
 */
function showTransferModal(provinceId) {
    // Will be implemented in Phase 4
    alert('Fund transfer not yet implemented');
}

/**
 * Switch main view
 */
function showView(viewName) {
    // Hide all views
    const views = [
        'province-list',
        'financial-report-view',
        'national-status-view',
        'budget-execution-view',
        'fund-management-view'
    ];
    
    views.forEach(view => {
        const element = document.getElementById(view);
        if (element) {
            if (view === 'province-list') {
                element.style.display = viewName === 'province-list' ? 'grid' : 'none';
            } else {
                element.style.display = view === `${viewName}-view` ? 'block' : 'none';
            }
        }
    });
    
    currentView = viewName;
    
    // Load view content if needed
    if (viewName !== 'province-list') {
        loadViewContent(viewName);
    }
}

/**
 * Load content for a specific view
 */
async function loadViewContent(viewName) {
    const viewElement = document.getElementById(`${viewName}-view`);
    const contentElement = viewElement.querySelector('.view-content');
    
    try {
        switch (viewName) {
            case 'financial-report':
                await loadFinancialReport(contentElement);
                break;
            case 'national-status':
                await loadNationalStatus(contentElement);
                break;
            case 'budget-execution':
                await loadBudgetExecution(contentElement);
                break;
            case 'fund-management':
                await loadFundManagement(contentElement);
                break;
        }
    } catch (error) {
        console.error('Error loading view:', error);
        contentElement.innerHTML = '<p class="error">Failed to load content</p>';
    }
}

/**
 * Load financial report content
 */
async function loadFinancialReport(container) {
    try {
        const response = await fetch('/api/financial-report');
        const data = await response.json();
        
        // Will be implemented in Phase 3.3
        container.innerHTML = '<p>Financial report loading...</p>';
    } catch (error) {
        container.innerHTML = '<p class="error">Failed to load financial report</p>';
    }
}

/**
 * Load national status content
 */
async function loadNationalStatus(container) {
    // Will be implemented in Phase 3.4
    container.innerHTML = '<p>National status loading...</p>';
}

/**
 * Load budget execution content
 */
async function loadBudgetExecution(container) {
    // Will be implemented in Phase 3.5
    container.innerHTML = '<p>Budget execution loading...</p>';
}

/**
 * Load fund management content
 */
async function loadFundManagement(container) {
    // Will be implemented in Phase 4
    container.innerHTML = '<p>Fund management loading...</p>';
}

/**
 * Advance to next month
 */
async function nextMonth() {
    const button = document.querySelector('button[onclick="nextMonth()"]');
    button.classList.add('loading');
    button.textContent = 'Processing...';
    
    try {
        const response = await fetch('/api/next-month', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // Reload page to show new state
            window.location.reload();
        } else {
            alert(result.detail || 'Failed to advance month');
            button.classList.remove('loading');
            button.textContent = 'Next Month';
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while advancing month');
        button.classList.remove('loading');
        button.textContent = 'Next Month';
    }
}

/**
 * Toggle debug mode
 */
async function toggleDebugMode() {
    try {
        const response = await fetch('/api/debug-mode', {
            method: 'POST'
        });
        
        if (response.ok) {
            // Reload page to show updated view
            window.location.reload();
        } else {
            alert('Failed to toggle debug mode');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred');
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Debug mode toggle
    const debugToggle = document.getElementById('debug-toggle');
    if (debugToggle) {
        debugToggle.addEventListener('change', toggleDebugMode);
    }
    
    // Close modal when clicking outside
    window.onclick = function(event) {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
            currentProvinceId = null;
        }
    };
});
