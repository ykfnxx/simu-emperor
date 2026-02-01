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
 * Show province events
 */
async function showProvinceEvents(provinceId) {
    try {
        const response = await fetch(`/api/events?province_id=${provinceId}`);
        const events = await response.json();
        
        if (events.length === 0) {
            alert('No active events for this province');
            return;
        }
        
        let message = 'Active Events:\n\n';
        events.forEach(event => {
            message += `• ${event.name} (Severity: ${event.severity})\n`;
            message += `  ${event.description}\n\n`;
        });
        
        alert(message);
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to load events');
    }
}

/**
 * Show transfer modal
 */
function showTransferModal(provinceId) {
    currentProvinceId = provinceId;
    
    // Get province name
    const provinceCard = document.querySelector(`[data-province-id="${provinceId}"]`);
    const provinceName = provinceCard.querySelector('.province-name').textContent;
    
    // Create simple prompt for amount
    const amount = prompt(`Transfer funds for ${provinceName}\nEnter amount (positive = to province, negative = from province):`);
    
    if (amount === null) return;
    
    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount === 0) {
        alert('Invalid amount');
        return;
    }
    
    if (numAmount > 0) {
        // Transfer to province
        submitTransferToProvince(provinceId, numAmount);
    } else {
        // Transfer from province
        submitTransferFromProvince(provinceId, Math.abs(numAmount));
    }
}

/**
 * Submit transfer to province
 */
async function submitTransferToProvince(provinceId, amount) {
    try {
        const response = await fetch('/api/transfer/to-province', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                province_id: provinceId,
                amount: amount
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert('Transfer successful!');
            window.location.reload();
        } else {
            alert(result.detail || 'Transfer failed');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred');
    }
}

/**
 * Submit transfer from province
 */
async function submitTransferFromProvince(provinceId, amount) {
    try {
        const response = await fetch('/api/transfer/from-province', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                province_id: provinceId,
                amount: amount
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert('Transfer successful!');
            window.location.reload();
        } else {
            alert(result.detail || 'Transfer failed');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred');
    }
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
        
        let html = `
            <div class="report-summary">
                <p><strong>Month Start:</strong> ${data.month_starting_treasury.toFixed(2)} gold</p>
                <p><strong>Month End:</strong> ${data.treasury.toFixed(2)} gold</p>
                <p><strong>Monthly Change:</strong> ${(data.monthly_change >= 0 ? '+' : '') + data.monthly_change.toFixed(2)} gold</p>
            </div>
            <h3>Provincial Reports</h3>
            <div class="report-provinces">
        `;
        
        data.provinces.forEach(p => {
            const corruptionWarning = p.last_month_corrupted ? 
                `<span class="warning">⚠️ Concealing ${(p.actual_income - p.reported_income).toFixed(2)} gold!</span>` : '';
            
            if (data.debug_mode) {
                html += `
                    <div class="report-province">
                        <h4>${p.name}</h4>
                        <p>Income: ${p.reported_income.toFixed(2)} / ${p.actual_income.toFixed(2)} gold</p>
                        <p>Expenditure: ${p.reported_expenditure.toFixed(2)} / ${p.actual_expenditure.toFixed(2)} gold</p>
                        <p>Surplus: ${p.reported_surplus.toFixed(2)} / ${p.actual_surplus.toFixed(2)} gold</p>
                        ${corruptionWarning}
                    </div>
                `;
            } else {
                const abnormalClass = p.last_month_corrupted ? 'abnormal' : '';
                html += `
                    <div class="report-province ${abnormalClass}">
                        <h4>${p.name}</h4>
                        <p>Income: ${p.reported_income.toFixed(2)} gold</p>
                        <p>Expenditure: ${p.reported_expenditure.toFixed(2)} gold</p>
                        <p>Surplus: ${p.reported_surplus.toFixed(2)} gold ${p.last_month_corrupted ? '[Abnormal]' : ''}</p>
                    </div>
                `;
            }
        });
        
        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<p class="error">Failed to load financial report</p>';
    }
}

/**
 * Load national status content
 */
async function loadNationalStatus(container) {
    try {
        const response = await fetch('/api/national-status');
        const data = await response.json();
        
        let html = `
            <div class="status-section">
                <h3>Treasury Overview</h3>
                <p>Current Treasury: <span class="gold">${data.treasury.toFixed(2)}</span> gold</p>
                <p>Actual Surplus: ${data.actual_surplus >= 0 ? '+' : ''}${data.actual_surplus.toFixed(2)} gold</p>
                <p>Reported Surplus: ${data.reported_surplus >= 0 ? '+' : ''}${data.reported_surplus.toFixed(2)} gold</p>
            </div>
            
            <div class="status-section">
                <h3>Provincial Overview (${data.province_count} provinces)</h3>
                <div class="province-grid">
        `;
        
        data.provinces.forEach(p => {
            const statusClass = p.last_month_corrupted ? 'warning' : '';
            html += `
                <div class="province-mini ${statusClass}">
                    <h4>${p.name}</h4>
                    <p>Pop: ${p.population.toLocaleString()}</p>
                    <p>Dev: ${p.development_level} | Loy: ${p.loyalty} | Stab: ${p.stability}</p>
                    <p>Income: ${p.reported_income.toFixed(2)} gold</p>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
            
            <div class="status-section">
                <h3>Active Events (${data.active_events.length})</h3>
        `;
        
        if (data.active_events.length === 0) {
            html += '<p>No active events</p>';
        } else {
            html += '<ul class="event-list">';
            data.active_events.forEach(e => {
                const typeLabel = e.event_type === 'national' ? '[National]' : `[${e.name}]`;
                html += `<li>${typeLabel} ${e.name} (Severity: ${e.severity})</li>`;
            });
            html += '</ul>';
        }
        
        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<p class="error">Failed to load national status</p>';
    }
}

/**
 * Load budget execution content
 */
async function loadBudgetExecution(container) {
    try {
        const response = await fetch('/api/budget');
        const data = await response.json();
        
        let html = `<h3>Year ${data.year}, Month ${data.month}</h3>`;
        
        // National budget
        html += '<div class="budget-section"><h4>Central Budget</h4>';
        if (data.national) {
            const rate = data.national.execution_rate.toFixed(1);
            html += `
                <div class="budget-bar">
                    <div class="budget-progress" style="width: ${Math.min(rate, 100)}%"></div>
                </div>
                <p>Budget: ${data.national.allocated.toFixed(2)} | 
                   Executed: ${data.national.spent.toFixed(2)} | 
                   Remaining: ${data.national.remaining.toFixed(2)} | 
                   Rate: ${rate}%</p>
            `;
        } else {
            html += '<p>No budget data available</p>';
        }
        html += '</div>';
        
        // Provincial budgets
        html += '<div class="budget-section"><h4>Provincial Budgets</h4>';
        if (data.provinces.length > 0) {
            data.provinces.forEach(p => {
                const rate = p.execution_rate.toFixed(1);
                html += `
                    <div class="budget-item">
                        <h5>${p.name}</h5>
                        <div class="budget-bar">
                            <div class="budget-progress" style="width: ${Math.min(rate, 100)}%"></div>
                        </div>
                        <p>Budget: ${p.allocated.toFixed(2)} | 
                           Executed: ${p.spent.toFixed(2)} | 
                           Rate: ${rate}%</p>
                    </div>
                `;
            });
        } else {
            html += '<p>No provincial budget data available</p>';
        }
        html += '</div>';
        
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<p class="error">Failed to load budget execution</p>';
    }
}

/**
 * Load fund management content
 */
async function loadFundManagement(container) {
    container.innerHTML = `
        <div class="fund-management">
            <div class="fund-tabs">
                <button onclick="showFundTab('transfer-to')" class="fund-tab active">Transfer to Province</button>
                <button onclick="showFundTab('transfer-from')" class="fund-tab">Transfer from Province</button>
                <button onclick="showFundTab('allocation')" class="fund-tab">Allocation Ratios</button>
                <button onclick="showFundTab('transactions')" class="fund-tab">Transactions</button>
            </div>
            <div class="fund-content" id="fund-content">
                <p>Loading...</p>
            </div>
        </div>
    `;
    
    // Load default tab
    showFundTab('transfer-to');
}

/**
 * Show fund management tab
 */
async function showFundTab(tabName) {
    const content = document.getElementById('fund-content');
    const tabs = document.querySelectorAll('.fund-tab');
    
    // Update tab styles
    tabs.forEach(tab => {
        tab.classList.remove('active');
        if (tab.textContent.toLowerCase().includes(tabName.replace('-', ' '))) {
            tab.classList.add('active');
        }
    });
    
    try {
        switch (tabName) {
            case 'transfer-to':
                await loadTransferToTab(content);
                break;
            case 'transfer-from':
                await loadTransferFromTab(content);
                break;
            case 'allocation':
                await loadAllocationTab(content);
                break;
            case 'transactions':
                await loadTransactionsTab(content);
                break;
        }
    } catch (error) {
        content.innerHTML = '<p class="error">Failed to load tab content</p>';
    }
}

/**
 * Load transfer to province tab
 */
async function loadTransferToTab(container) {
    const response = await fetch('/api/provinces');
    const provinces = await response.json();
    
    let html = `
        <h4>Transfer from National to Province</h4>
        <div class="transfer-form">
            <label>Province:</label>
            <select id="transfer-to-province">
    `;
    
    provinces.forEach(p => {
        html += `<option value="${p.province_id}">${p.name}</option>`;
    });
    
    html += `
            </select>
            <label>Amount:</label>
            <input type="number" id="transfer-to-amount" min="1" step="1">
            <button onclick="executeTransferTo()">Transfer</button>
        </div>
    `;
    
    container.innerHTML = html;
}

/**
 * Load transfer from province tab
 */
async function loadTransferFromTab(container) {
    const response = await fetch('/api/provinces');
    const provinces = await response.json();
    
    // Get balances
    const balances = await Promise.all(
        provinces.map(p => fetch(`/api/provinces/${p.province_id}/balance`).then(r => r.json()))
    );
    
    let html = `
        <h4>Transfer from Province to National</h4>
        <div class="transfer-form">
            <label>Province:</label>
            <select id="transfer-from-province">
    `;
    
    provinces.forEach((p, i) => {
        html += `<option value="${p.province_id}">${p.name} (Balance: ${balances[i].balance.toFixed(2)})</option>`;
    });
    
    html += `
            </select>
            <label>Amount:</label>
            <input type="number" id="transfer-from-amount" min="1" step="1">
            <button onclick="executeTransferFrom()">Transfer</button>
        </div>
    `;
    
    container.innerHTML = html;
}

/**
 * Load allocation ratios tab
 */
async function loadAllocationTab(container) {
    const response = await fetch('/api/allocation-ratios');
    const ratios = await response.json();
    
    let html = '<h4>Set Surplus Allocation Ratios</h4><p class="hint">Ratio = share to national (0.0 = keep all local, 1.0 = transfer all)</p>';
    
    html += '<div class="allocation-list">';
    ratios.forEach(r => {
        html += `
            <div class="allocation-item">
                <span>${r.name}</span>
                <input type="range" min="0" max="1" step="0.1" value="${r.ratio}" 
                       onchange="updateAllocationRatio(${r.province_id}, this.value)"
                       id="ratio-${r.province_id}">
                <span id="ratio-display-${r.province_id}">${(r.ratio * 100).toFixed(0)}% to national</span>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

/**
 * Load transactions tab
 */
async function loadTransactionsTab(container) {
    const response = await fetch('/api/transactions/national?limit=10');
    const data = await response.json();
    
    let html = '<h4>National Treasury Transactions (Last 10)</h4>';
    
    if (data.transactions.length === 0) {
        html += '<p>No transactions</p>';
    } else {
        html += '<table class="transaction-table"><thead><tr><th>Date</th><th>Type</th><th>Amount</th><th>Balance</th></tr></thead><tbody>';
        data.transactions.forEach(t => {
            const date = `${t.year}-${String(t.month).padStart(2, '0')}`;
            const amountClass = t.amount >= 0 ? 'positive' : 'negative';
            html += `
                <tr>
                    <td>${date}</td>
                    <td>${t.type}</td>
                    <td class="${amountClass}">${t.amount >= 0 ? '+' : ''}${t.amount.toFixed(2)}</td>
                    <td>${t.balance_after.toFixed(2)}</td>
                </tr>
            `;
        });
        html += '</tbody></table>';
    }
    
    container.innerHTML = html;
}

/**
 * Execute transfer to province
 */
async function executeTransferTo() {
    const provinceId = document.getElementById('transfer-to-province').value;
    const amount = parseFloat(document.getElementById('transfer-to-amount').value);
    
    if (!amount || amount <= 0) {
        alert('Please enter a valid amount');
        return;
    }
    
    await submitTransferToProvince(parseInt(provinceId), amount);
}

/**
 * Execute transfer from province
 */
async function executeTransferFrom() {
    const provinceId = document.getElementById('transfer-from-province').value;
    const amount = parseFloat(document.getElementById('transfer-from-amount').value);
    
    if (!amount || amount <= 0) {
        alert('Please enter a valid amount');
        return;
    }
    
    await submitTransferFromProvince(parseInt(provinceId), amount);
}

/**
 * Update allocation ratio
 */
async function updateAllocationRatio(provinceId, ratio) {
    try {
        const response = await fetch(`/api/allocation-ratios/${provinceId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ ratio: parseFloat(ratio) })
        });
        
        if (response.ok) {
            document.getElementById(`ratio-display-${provinceId}`).textContent = 
                `${(ratio * 100).toFixed(0)}% to national`;
        } else {
            alert('Failed to update ratio');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred');
    }
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
