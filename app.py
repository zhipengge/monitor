from flask import Flask, render_template, jsonify
from hardware_info import HardwareInfo

app = Flask(__name__)
hardware_info = HardwareInfo()

@app.route('/')
def index():
    data = hardware_info.get_all_info()
    temps_dict = data.get('temperatures', {})
    cpu_temps = []
    for key, val in temps_dict.items():
        if 'core' in key.lower() and 'temp' in key.lower():
            cpu_temps.append(val['value'])
    return render_template('index.html', cpu_core_temps=cpu_temps)

@app.route('/api/hardware_info')
def get_hardware_info():
    return jsonify(hardware_info.get_all_info())

if __name__ == '__main__':
    app.run(debug=True)
