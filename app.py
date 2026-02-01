from flask import Flask, render_template, jsonify
from hardware_info import HardwareInfo
import traceback
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__, 
            static_folder='static',  # 显式指定静态文件夹
            template_folder='templates')  # 显式指定模板文件夹
hardware_info = HardwareInfo()

# 在创建app后，添加自定义函数
app.jinja_env.globals.update(min=min)

# 全局辅助函数
def convert_to_number(value):
    """将值转换为数字类型"""
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0

def safe_division(numerator, denominator, default=0):
    """安全除法，避免除以零错误"""
    try:
        num = float(numerator) if numerator is not None else 0
        denom = float(denominator) if denominator is not None else 0
        
        if denom == 0:
            return default
        return (num / denom) * 100
    except (ValueError, TypeError):
        return default

def prepare_template_data(data):
    """准备模板数据"""
    # 提取CPU信息
    cpu_info = data.get('cpu', {})
    cpu_usage = cpu_info.get('usage_per_core', [])
    
    # 提取内存信息
    memory = data.get('memory', {})
    
    # 提取温度信息
    temps = data.get('temperatures', {})
    cpu_temps = [(int(key.split(" ")[-1]), key, val.get('value', 0)) for key, val in temps.items() if 'core' in key.lower()]
    cpu_temps.sort(key=lambda x: x[0])
    cpu_temps = [{"name": x[1], "value": x[2]} for x in cpu_temps]
    # 处理内存数据
    mem_total = convert_to_number(memory.get('total', 0))
    mem_used = convert_to_number(memory.get('used', 0))
    mem_percent = convert_to_number(memory.get('percent', 0))
    
    # 准备基础数据
    template_data = {
        'cpu_percent': cpu_info.get('total_usage', 0),
        'cpu_name': cpu_info.get('name', 'Unknown CPU'),
        'cpu_cores': cpu_info.get('cores', 0),
        'cpu_usage_per_core': cpu_usage,
        'cpu_temps': cpu_temps,
        'mem_percent': mem_percent,
        'mem_total': mem_total,
        'mem_used': mem_used,
        'temperatures': temps,
        'gpu_info': data.get('gpu', []),
        'disks': data.get('disk', []),
        'system': data.get('system', {})
    }
    
    # 计算GPU内存使用率 - 增加错误处理
    try:
        gpu_info = data.get('gpu', [])
        if gpu_info:
            logging.info(f"GPU信息: {len(gpu_info)}个GPU设备")
            
        for i, gpu in enumerate(gpu_info):
            if isinstance(gpu, dict) and 'memory' in gpu:
                memory_percent = safe_division(
                    gpu['memory'].get('used'), 
                    gpu['memory'].get('total')
                )
                if 'memory' in template_data['gpu_info'][i]:
                    template_data['gpu_info'][i]['memory']['percent'] = round(memory_percent)
                else:
                    template_data['gpu_info'][i]['memory'] = {'percent': round(memory_percent)}
    except Exception as e:
        logging.error(f"处理GPU数据时出错: {str(e)}")
        logging.error(traceback.format_exc())
    
    return template_data

@app.route('/')
def index():
    try:
        # 获取硬件信息并准备数据
        data = hardware_info.get_all_info()
        template_data = prepare_template_data(data)
        
        logging.info(f"主页加载 - CPU: {template_data['cpu_name']}, 核心数: {len(template_data['cpu_usage_per_core'])}")
        
        return render_template('dashboard.html', **template_data)
    except Exception as e:
        logging.error(f"主页加载错误: {str(e)}")
        logging.error(traceback.format_exc())
        return f"发生错误: {str(e)}", 500

@app.route('/api/hardware_info')
def api_hardware_info():
    """提供硬件信息API接口"""
    hw_info = hardware_info.get_all_info()  # 重命名变量
    return jsonify(hw_info)

@app.route('/dashboard')
def dashboard():
    # 获取硬件信息并准备数据
    data = hardware_info.get_all_info()
    template_data = prepare_template_data(data)
    
    print("Dashboard路由访问")
    return render_template('dashboard.html', **template_data)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

if __name__ == '__main__':
    app.run(debug=True)
