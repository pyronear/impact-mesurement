// Load data summary on page load
document.addEventListener('DOMContentLoaded', function() {
    loadDataSummary();
    loadDepartments();
});

// Load and display dataset summary
function loadDataSummary() {
    fetch('/api/data-summary')
        .then(response => response.json())
        .then(data => {
            const html = `
                <div class="stat-card">
                    <div class="stat-label">Total Fires</div>
                    <div class="stat-value">${data.total_fires.toLocaleString()}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Area Burned</div>
                    <div class="stat-value">${data.total_area_ha.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                    <div class="stat-unit">hectares</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Average Fire Size</div>
                    <div class="stat-value">${data.mean_fire_size.toFixed(2)}</div>
                    <div class="stat-unit">hectares</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Largest Fire</div>
                    <div class="stat-value">${data.max_fire_size.toLocaleString(undefined, {maximumFractionDigits: 0})}</div>
                    <div class="stat-unit">hectares</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Dataset</div>
                    <div class="stat-value" style="font-size: 1.2em;">${data.dataset_name}</div>
                </div>
            `;
            
            document.getElementById('dataset-info').innerHTML = html;
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('dataset-info').innerHTML = '<p>Error loading dataset</p>';
        });
}

// Load departments list
function loadDepartments() {
    fetch('/api/departments')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('department');
            select.innerHTML = '';
            data.departments.forEach(dept => {
                const option = document.createElement('option');
                option.value = dept;
                option.textContent = dept === 'default' ? 'Default (National Average)' : `Department ${dept}`;
                select.appendChild(option);
            });
        })
        .catch(error => console.error('Error loading departments:', error));
}

// Upload CSV file
function uploadFile() {
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    
    if (!file) {
        showStatus('Please select a file', 'error', 'upload-status');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    const statusDiv = document.getElementById('upload-status');
    statusDiv.innerHTML = '<div class="spinner"></div> Uploading...';
    
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showStatus('Error: ' + data.error, 'error', 'upload-status');
        } else {
            showStatus(`✓ Uploaded "${data.filename}" with ${data.total_records} records`, 'success', 'upload-status');
            fileInput.value = '';
            loadDataSummary();
            loadDepartments();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showStatus('Upload failed: ' + error, 'error', 'upload-status');
    });
}

// Calculate wildfire impact
function calculateImpact() {
    const params = {
        minutes_saved: parseFloat(document.getElementById('minutes-saved').value),
        response_time: parseFloat(document.getElementById('response-time').value),
        wind_speed: parseFloat(document.getElementById('wind-speed').value),
        temperature: parseFloat(document.getElementById('temperature').value),
        humidity: parseFloat(document.getElementById('humidity').value),
        department: document.getElementById('department').value,
        vegetation: document.getElementById('vegetation').value || null,
    };
    
    fetch('/api/calculate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(params)
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            const impact = data.impact;
            
            // Display results
            document.getElementById('result-direct').textContent = impact.direct_ha.toFixed(2);
            document.getElementById('result-total').textContent = impact.total_ha.toFixed(2);
            document.getElementById('result-co2').textContent = impact.tco2.toLocaleString(undefined, {maximumFractionDigits: 0});
            document.getElementById('result-value').textContent = '€' + impact.value_euros.toLocaleString(undefined, {maximumFractionDigits: 0});
            document.getElementById('result-buildings').textContent = impact.buildings;
            document.getElementById('result-veg').textContent = impact.vegetation.replace(/_/g, ' ');
            
            document.getElementById('results-panel').style.display = 'block';
            document.getElementById('scenario-panel').style.display = 'block';
            document.getElementById('export-panel').style.display = 'block';
            
            // Save results for export
            window.lastResults = [impact];
            
            // Scroll to results
            document.getElementById('results-panel').scrollIntoView({behavior: 'smooth'});
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Calculation failed: ' + error);
    });
}

// Generate scenario analysis
function generateScenarios() {
    const params = {
        minutes_list: [5, 10, 15, 20, 30],
        department: document.getElementById('department').value,
        vegetation: document.getElementById('vegetation').value || null,
    };
    
    fetch('/api/scenarios', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(params)
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
        } else {
            displayScenarios(data.scenarios);
            displayScenarioChart(data.scenarios);
            window.lastResults = data.scenarios;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Scenario analysis failed: ' + error);
    });
}

// Display scenario results as table
function displayScenarios(scenarios) {
    let html = `
        <table>
            <thead>
                <tr>
                    <th>Minutes Saved</th>
                    <th>Direct Ha Saved</th>
                    <th>Risk-Adjusted Ha</th>
                    <th>tCO₂ Avoided</th>
                    <th>Value €</th>
                    <th>Buildings</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    scenarios.forEach(scenario => {
        html += `
            <tr>
                <td>${scenario['Minutes Saved']}</td>
                <td>${scenario['Ha Saved (Direct)'].toFixed(2)}</td>
                <td>${scenario['Ha Saved (Risk-Adjusted)'].toFixed(2)}</td>
                <td>${scenario['tCO2 Avoided'].toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
                <td>€${scenario['€ Value Avoided'].toLocaleString(undefined, {maximumFractionDigits: 0})}</td>
                <td>${scenario['Buildings Protected']}</td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    document.getElementById('scenario-table-container').innerHTML = html;
}

// Display scenario chart
function displayScenarioChart(scenarios) {
    const ctx = document.getElementById('scenario-chart').getContext('2d');
    
    const labels = scenarios.map(s => s['Minutes Saved'] + ' min');
    const haData = scenarios.map(s => s['Ha Saved (Risk-Adjusted)']);
    const co2Data = scenarios.map(s => s['tCO2 Avoided']);
    const valueData = scenarios.map(s => s['€ Value Avoided'] / 1000); // Convert to thousands
    
    // Destroy existing chart if it exists
    if (window.scenarioChart) {
        window.scenarioChart.destroy();
    }
    
    window.scenarioChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Hectares Saved',
                    data: haData,
                    borderColor: '#d32f2f',
                    backgroundColor: 'rgba(211, 47, 47, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y',
                },
                {
                    label: 'tCO₂ Prevented',
                    data: co2Data,
                    borderColor: '#1976d2',
                    backgroundColor: 'rgba(25, 118, 210, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y1',
                },
                {
                    label: 'Value (€K)',
                    data: valueData,
                    borderColor: '#388e3c',
                    backgroundColor: 'rgba(56, 142, 60, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y',
                },
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Impact vs. Early Detection Time Savings'
                },
                legend: {
                    display: true,
                    position: 'top',
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Hectares / Value (€K)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'tCO₂'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                },
            }
        }
    });
}

// Export results as CSV
function exportResults() {
    if (!window.lastResults || window.lastResults.length === 0) {
        alert('No results to export');
        return;
    }
    
    fetch('/api/export-results', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({results: window.lastResults})
    })
    .then(response => response.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'wildfire_impact_results.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Export failed: ' + error);
    });
}

// Show status messages
function showStatus(message, type, elementId) {
    const statusDiv = document.getElementById(elementId);
    statusDiv.className = 'status-message ' + type;
    statusDiv.textContent = message;
}
