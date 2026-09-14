"""
Wildfire Impact Calculator Web Application
Flask-based interactive tool for calculating early detection impact using fire datasets
"""

import os
import json
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import traceback
from wildfire_impact_calculator import WildfireImpactCalculator
import io

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create uploads folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variables for current dataset
current_calculator = None
current_data = None
current_filename = None

# Load default BDIFF dataset on startup
def load_default_data():
    """Load BDIFF dataset on app startup."""
    global current_calculator, current_data, current_filename
    try:
        bdiff_path = 'Incendies.csv'
        if os.path.exists(bdiff_path):
            current_calculator = WildfireImpactCalculator(bdiff_path)
            current_data = pd.read_csv(bdiff_path, encoding='utf-8', sep=';', skiprows=2)
            current_data['hectares'] = pd.to_numeric(
                current_data['Surface parcourue (m2)'], errors='coerce'
            ) / 10000
            current_filename = 'BDIFF 2025 (Default)'
            return True
    except Exception as e:
        print(f"Error loading default data: {e}")
    return False

@app.route('/')
def index():
    """Main dashboard page."""
    if current_data is None:
        return render_template('error.html', message='No dataset loaded. Please upload a CSV file.'), 500
    
    # Get dataset stats
    stats = {
        'total_fires': len(current_data),
        'total_area_ha': current_data['hectares'].sum() if 'hectares' in current_data.columns else 0,
        'mean_size': current_data['hectares'].mean() if 'hectares' in current_data.columns else 0,
        'max_size': current_data['hectares'].max() if 'hectares' in current_data.columns else 0,
        'dataset_name': current_filename,
    }
    
    return render_template('index.html', stats=stats)

@app.route('/api/data-summary')
def data_summary():
    """Get summary statistics for current dataset."""
    if current_data is None:
        return jsonify({'error': 'No data loaded'}), 400
    
    data_dict = current_data.to_dict('records') if len(current_data) <= 1000 else current_data.head(1000).to_dict('records')
    
    # Get top departments
    if 'Département' in current_data.columns and 'hectares' in current_data.columns:
        top_depts = current_data.groupby('Département')['hectares'].agg(['sum', 'count']).sort_values('sum', ascending=False).head(10)
        dept_summary = [
            {'dept': dept, 'total_ha': float(row['sum']), 'fires': int(row['count'])}
            for dept, row in top_depts.iterrows()
        ]
    else:
        dept_summary = []
    
    return jsonify({
        'total_fires': len(current_data),
        'total_area_ha': float(current_data['hectares'].sum() if 'hectares' in current_data.columns else 0),
        'mean_fire_size': float(current_data['hectares'].mean() if 'hectares' in current_data.columns else 0),
        'max_fire_size': float(current_data['hectares'].max() if 'hectares' in current_data.columns else 0),
        'dataset_name': current_filename,
        'top_departments': dept_summary,
        'columns': list(current_data.columns),
        'sample_data': data_dict[:50],  # Send first 50 rows
    })

@app.route('/api/calculate', methods=['POST'])
def calculate_impact():
    """Calculate wildfire impact for given parameters."""
    try:
        if current_calculator is None:
            return jsonify({'error': 'No calculator available. Dataset not loaded.'}), 400
        
        data = request.json
        
        # Get parameters
        minutes_saved = float(data.get('minutes_saved', 15))
        response_time = float(data.get('response_time', 45))
        wind_speed = float(data.get('wind_speed', 25))
        temperature = float(data.get('temperature', 28))
        humidity = float(data.get('humidity', 35))
        dept = data.get('department', 'default')
        veg_type = data.get('vegetation', None)
        
        # Calculate impact
        impact = current_calculator.calculate_impact(
            x_minutes_saved=minutes_saved,
            t0_response_time=response_time,
            wind_speed_kmh=wind_speed,
            temperature_C=temperature,
            relative_humidity_pct=humidity,
            dept=dept,
            vegetation_type=veg_type
        )
        
        return jsonify({
            'success': True,
            'impact': {
                'minutes_saved': impact['minutes_saved'],
                'direct_ha': round(impact['direct_area_saved_ha'], 3),
                'total_ha': round(impact['risk_adjusted_ha_saved'], 3),
                'tco2': round(impact['tco2_emissions_prevented'], 2),
                'value_euros': round(impact['economic_value_avoided_euros'], 2),
                'buildings': impact['buildings_protected'],
                'vegetation': impact['vegetation_type'],
                'wind_category': impact['wind_category'],
                'suppression_cost_per_ha': impact.get('suppression_cost_per_ha', 0),
                'asset_value_per_ha': impact.get('asset_value_per_ha', 0),
                'cost_source': impact.get('cost_source', 'BDIFF historical'),
            }
        })
    
    except Exception as e:
        print(f"Error in calculate: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 400

@app.route('/api/scenarios', methods=['POST'])
def scenarios():
    """Generate scenario analysis."""
    try:
        if current_calculator is None:
            return jsonify({'error': 'No calculator available'}), 400
        
        data = request.json
        minutes_list = data.get('minutes_list', [5, 10, 15, 20, 30])
        dept = data.get('department', 'default')
        veg_type = data.get('vegetation', None)
        
        results_df = current_calculator.scenario_analysis(
            minutes_saved_list=minutes_list,
            dept=dept,
            vegetation_type=veg_type
        )
        
        results = results_df.to_dict('records')
        
        return jsonify({
            'success': True,
            'scenarios': results
        })
    
    except Exception as e:
        print(f"Error in scenarios: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle CSV file upload."""
    try:
        global current_calculator, current_data, current_filename
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are supported'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Try to load the file
        try:
            # Try common delimiters
            for delimiter in [';', ',', '\t']:
                try:
                    df = pd.read_csv(filepath, encoding='utf-8', sep=delimiter, skiprows=2)
                    if len(df.columns) > 1:
                        break
                except:
                    continue
            
            # Calculate hectares if area column exists
            area_cols = [col for col in df.columns if 'area' in col.lower() or 'surface' in col.lower() or 'ha' in col.lower()]
            if area_cols:
                area_col = area_cols[0]
                df['hectares'] = pd.to_numeric(df[area_col], errors='coerce')
                # If in m², convert to hectares
                if df['hectares'].max() > 50000:  # Likely in m²
                    df['hectares'] = df['hectares'] / 10000
            else:
                df['hectares'] = 0
            
            # Update global variables
            current_calculator = WildfireImpactCalculator(filepath)
            current_data = df
            current_filename = filename
            
            return jsonify({
                'success': True,
                'filename': filename,
                'total_records': len(df),
                'total_area': float(df['hectares'].sum()),
                'columns': list(df.columns)
            })
        
        except Exception as e:
            os.remove(filepath)
            return jsonify({'error': f'Failed to parse CSV: {str(e)}'}), 400
    
    except Exception as e:
        print(f"Error in upload: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/departments')
def get_departments():
    """Get list of departments from current data."""
    if current_data is None or 'Département' not in current_data.columns:
        return jsonify({'departments': ['default']})
    
    depts = sorted(current_data['Département'].unique().astype(str).tolist())
    return jsonify({'departments': ['default'] + depts})

@app.route('/api/export-results', methods=['POST'])
def export_results():
    """Export calculation results as CSV."""
    try:
        data = request.json
        results = data.get('results', [])
        
        if not results:
            return jsonify({'error': 'No results to export'}), 400
        
        df = pd.DataFrame(results)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='wildfire_impact_results.csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    # Load default dataset
    if load_default_data():
        print("✓ Default BDIFF dataset loaded")
    else:
        print("⚠ No default dataset found. Please upload a CSV file.")
    
    # Run app
    app.run(debug=True, host='0.0.0.0', port=5000)
