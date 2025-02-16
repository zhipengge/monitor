from flask import Flask, render_template, jsonify
from hardware_info import HardwareInfo
import time

app = Flask(__name__)
hardware_info = HardwareInfo()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/hardware_info')
def get_hardware_info():
    return jsonify(hardware_info.get_all_info())

if __name__ == '__main__':
    app.run(debug=True) 