╔══════════════════════════════════════════════════════════════════════════════╗
║                  WILDFIRE IMPACT CALCULATOR - WEB APP GUIDE                  ║
║                                                                              ║
║                    Interactive Dashboard for Fire Analysis                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════

🚀 GETTING STARTED

1. Install Flask dependencies:
   ─────────────────────────────
   cd '/Users/doconnor/Desktop/untitled folder'
   source venv/bin/activate
   pip install -r requirements-webapp.txt

2. Start the web server:
   ──────────────────────
   python3 app.py

3. Open in browser:
   ────────────────
   http://localhost:5000

═══════════════════════════════════════════════════════════════════════════════

📊 FEATURES

✓ DATASET MANAGEMENT
  • View current dataset statistics (total fires, area burned, etc.)
  • Upload custom CSV files with fire data
  • Automatic delimiter detection (semicolon, comma, tab)
  • Automatic hectare conversion from square meters

✓ IMPACT CALCULATOR
  • Adjust early detection time savings (5-120 minutes)
  • Configure standard response time (10-180 minutes)
  • Set weather conditions (wind, temperature, humidity)
  • Select French department or use national average
  • Auto-detect or manually select vegetation type

✓ RESULTS DISPLAY
  • 6 key metrics shown in cards:
    - Direct area saved (hectares)
    - Risk-adjusted area saved (hectares)
    - CO₂ emissions prevented (tCO₂)
    - Economic value protected (€)
    - Buildings protected (#)
    - Vegetation type classification

✓ SCENARIO ANALYSIS
  • Compare multiple early detection scenarios
  • Interactive results table
  • Multi-axis chart visualization
  • Sensitivity analysis built-in

✓ EXPORT
  • Download results as CSV
  • Spreadsheet-ready format

═══════════════════════════════════════════════════════════════════════════════

📁 PROJECT STRUCTURE

wildfire-calculator/
├── app.py                          # Flask backend (10 KB)
├── wildfire_impact_calculator.py   # Core calculation engine (14 KB)
│
├── templates/
│   ├── index.html                  # Main dashboard (8.8 KB)
│   └── error.html                  # Error page
│
├── static/
│   ├── css/
│   │   └── style.css              # Styling (6.5 KB)
│   └── js/
│       └── app.js                 # Frontend logic (12 KB)
│
├── Incendies.csv                   # BDIFF 2025 data (default)
├── uploads/                        # User-uploaded files
└── requirements-webapp.txt         # Python dependencies

═══════════════════════════════════════════════════════════════════════════════

🔧 BACKEND (Flask)

File: app.py (10 KB, 295 lines)

Main Routes:
────────────
GET  /                     → Load dashboard with dataset stats
GET  /api/data-summary     → Get current dataset statistics
POST /api/calculate        → Calculate single impact
POST /api/scenarios        → Generate scenario comparison
POST /api/upload           → Upload and parse CSV file
GET  /api/departments      → List available departments
POST /api/export-results   → Export results as CSV

Features:
─────────
• Automatic BDIFF dataset loading on startup
• CSV upload with flexible delimiter detection
• Hectare conversion from m² (if needed)
• Integration with WildfireImpactCalculator class
• JSON API responses
• File upload validation (max 50 MB)

═══════════════════════════════════════════════════════════════════════════════

🎨 FRONTEND (HTML/CSS/JavaScript)

Main Components:
────────────────

1. DATASET PANEL
   • Display: total fires, burned area, fire size stats
   • Upload: drag-drop or file select
   • Status: upload feedback

2. CALCULATOR PANEL
   • Inputs: 7 parameters (time, response, weather, location, vegetation)
   • Form validation
   • Real-time input feedback
   • Submit button

3. RESULTS PANEL
   • 6 metric cards with icons
   • Color-coded values
   • Responsive grid layout

4. SCENARIO PANEL
   • Interactive table (minutes saved vs. impacts)
   • Multi-axis chart (Chart.js)
   • Live updates

5. EXPORT PANEL
   • CSV download button
   • Results include all calculations

═══════════════════════════════════════════════════════════════════════════════

📊 DATA FORMAT REQUIREMENTS

For CSV uploads, the calculator looks for:

Required:
─────────
• Column with fire area (any of: "area", "surface", "ha", "hectares", m², etc.)
  → Automatically converted if in square meters

Optional (for full functionality):
──────────────────────────────────
• Département (French department code)
• Vegetation type or fire classification
• Fire cause/nature
• Building/casualty information

Example formats:
  • French style: Département;Surface parcourue (m2);Nature
  • English: Department,Burned Area (ha),Fire Cause
  • Mixed: Region, Area_m2, Vegetation_Type

═══════════════════════════════════════════════════════════════════════════════

🌐 HOW IT WORKS

Step 1: USER INPUT
   User enters parameters:
   • Minutes saved (e.g., 15)
   • Response time (e.g., 45)
   • Weather (wind, temp, humidity)
   • Location (department)
   • Vegetation type

Step 2: BACKEND PROCESSING
   Flask receives parameters
   ↓
   Instantiates WildfireImpactCalculator
   ↓
   Calls calculate_impact() method
   ↓
   Returns JSON with 5 impact metrics

Step 3: FRONTEND DISPLAY
   JavaScript receives JSON
   ↓
   Updates result cards with values
   ↓
   Shows panels and enables export

Step 4: OPTIONAL SCENARIOS
   User clicks "Compare Scenarios"
   ↓
   Flask calls scenario_analysis()
   ↓
   Returns table data + chart data
   ↓
   Chart.js renders visualization

═══════════════════════════════════════════════════════════════════════════════

🎯 USAGE EXAMPLES

Example 1: Default Dataset with Default Settings
────────────────────────────────────────────────
1. Load app at http://localhost:5000
2. App auto-loads BDIFF 2025 data
3. See dataset stats: 21,141 fires, 31,744 ha
4. All parameters pre-filled
5. Click "Calculate Impact"
6. View results: 35.1 ha saved, €368K value, etc.

Example 2: Custom Dataset Upload
───────────────────────────────
1. Click "Upload CSV"
2. Select your fire dataset (any format)
3. App auto-detects format and hectares conversion
4. Dataset reloaded with new data
5. Adjust parameters for your data
6. Calculate and export results

Example 3: Scenario Comparison
───────────────────────
1. Fill in parameters
2. Click "Calculate Impact"
3. Click "Compare Scenarios"
4. View table: impact across 5, 10, 15, 20, 30 minutes
5. Chart shows non-linear benefits
6. Download as CSV

═══════════════════════════════════════════════════════════════════════════════

⚙️ API RESPONSE EXAMPLES

Calculate Impact:
─────────────────
POST /api/calculate
{
  "minutes_saved": 15,
  "response_time": 45,
  "wind_speed": 35,
  "department": "06",
  "vegetation": "garrigue_maquis"
}

Response:
{
  "success": true,
  "impact": {
    "minutes_saved": 15,
    "direct_ha": 35.117,
    "total_ha": 35.117,
    "tco2": 363.11,
    "value_euros": 368725.59,
    "buildings": 35,
    "vegetation": "garrigue_maquis",
    "wind_category": "high"
  }
}

Scenarios:
──────────
POST /api/scenarios
{
  "minutes_list": [5, 10, 15, 20, 30],
  "department": "06",
  "vegetation": "garrigue_maquis"
}

Response:
{
  "success": true,
  "scenarios": [
    {
      "Minutes Saved": 5,
      "Ha Saved (Direct)": 5.896,
      "Ha Saved (Risk-Adjusted)": 5.896,
      "tCO2 Avoided": 60.97,
      "€ Value Avoided": 61909.5,
      "Buildings Protected": 5
    },
    ... (more scenarios)
  ]
}

═══════════════════════════════════════════════════════════════════════════════

🌍 DEPLOYMENT OPTIONS

Development (Current):
──────────────────────
python3 app.py
→ Debug mode enabled
→ Auto-reload on code changes
→ Localhost only (127.0.0.1:5000)

Production (Gunicorn):
──────────────────────
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
→ 4 worker processes
→ All interfaces (0.0.0.0)
→ Port 5000 (configurable)

Docker:
───────
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements-webapp.txt
CMD ["python", "app.py"]

Cloud Deployment:
─────────────────
• Heroku: gunicorn app:app
• AWS: ElasticBeanstalk
• Azure: App Service
• Google Cloud: Cloud Run

═══════════════════════════════════════════════════════════════════════════════

🐛 TROUBLESHOOTING

Issue: "ModuleNotFoundError: No module named 'flask'"
Solution:
  pip install -r requirements-webapp.txt

Issue: "Port 5000 already in use"
Solution:
  python3 app.py     # Check if already running
  pkill -f "python3 app.py"  # Kill existing process
  python3 app.py --port 5001  # Use different port

Issue: CSV upload fails with "Failed to parse CSV"
Solution:
  • Ensure file is .csv format
  • Check delimiter (;, ,, or \t)
  • Verify area column exists
  • Try with sample BDIFF file first

Issue: No results after calculation
Solution:
  • Check browser console for errors (F12)
  • Verify all parameters are valid numbers
  • Try default department first
  • Refresh page and reload data

═══════════════════════════════════════════════════════════════════════════════

📝 CUSTOMIZATION

Modify Default Parameters:
──────────────────────────
Edit static/js/app.js, look for:
  document.getElementById('minutes-saved').value = "15"  // Change to desired value

Change Default Department:
──────────────────────────
Edit static/js/app.js, change:
  department: document.getElementById('department').value

Change Color Scheme:
───────────────────
Edit static/css/style.css, modify --primary-color, --secondary-color:
  --primary-color: #d32f2f;  /* Red */
  --secondary-color: #1976d2; /* Blue */

Add New Vegetation Types:
─────────────────────────
Edit static/js/app.js in the vegetation select options
Also update wildfire_impact_calculator.py with new SPREAD_RATES and FUEL_CHARACTERISTICS

═══════════════════════════════════════════════════════════════════════════════

✅ TESTING CHECKLIST

Before deploying to production:

□ Load app with default BDIFF data
□ Verify all 6 results cards display correctly
□ Adjust each parameter independently
□ Verify results change appropriately
□ Test CSV upload with sample file
□ Verify scenario comparison works
□ Check chart visualization renders
□ Test export as CSV
□ Verify responsive design on mobile
□ Check console for JavaScript errors
□ Test with different departments
□ Verify error messages display correctly

═══════════════════════════════════════════════════════════════════════════════

📞 SUPPORT

If you encounter issues:

1. Check the console (F12 → Console tab)
2. Review app.py output for errors
3. Verify CSV format is correct
4. Test with BDIFF sample file first
5. Check all input values are valid numbers
6. Restart the Flask app

═══════════════════════════════════════════════════════════════════════════════

Version: 1.0
Last Updated: September 2026
Status: ✅ Production Ready
