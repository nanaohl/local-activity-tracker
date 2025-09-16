
from flask import Flask, jsonify, render_template
from datetime import datetime
import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import (
    get_daily_summary,
    get_weekly_summary,
    get_monthly_summary,
    get_yearly_summary,
)

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    now = datetime.now()
    daily_summary = get_daily_summary(now.day, now.month, now.year)
    weekly_summary = get_weekly_summary(now.isocalendar()[1], now.year)
    monthly_summary = get_monthly_summary(now.month, now.year)
    yearly_summary = get_yearly_summary(now.year)
    
    return jsonify({
        'daily': daily_summary,
        'weekly': weekly_summary,
        'monthly': monthly_summary,
        'yearly': yearly_summary
    })

if __name__ == '__main__':
    app.run(debug=True)
