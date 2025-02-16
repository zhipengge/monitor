import platform
import psutil
from datetime import datetime

class TemperatureMonitor:
    def __init__(self):
        self.system = platform.system()
        self.temp_info = {}
        
        # Windows系统初始化
        if self.system == "Windows":
            try:
                import wmi
                self.wmi = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            except:
                self.wmi = None
        
        # Linux系统初始化
        elif self.system == "Linux":
            try:
                import sensors
                sensors.init()
                self.sensors = sensors
            except:
                self.sensors = None
    
    def get_windows_temps(self):
        temps = {}
        if not self.wmi:
            return temps
            
        try:
            for sensor in self.wmi.Sensor():
                if sensor.SensorType == 'Temperature':
                    name = sensor.Name
                    value = sensor.Value
                    if value is not None:
                        temps[name] = {
                            'value': round(value, 1),
                            'max': getattr(sensor, 'Max', None),
                            'min': getattr(sensor, 'Min', None)
                        }
        except:
            pass
        return temps
    
    def get_linux_temps(self):
        temps = {}
        if not self.sensors:
            return temps
            
        try:
            for chip in self.sensors.iter_detected_chips():
                for feature in chip:
                    if feature.type == self.sensors.FEATURE_TEMP:
                        name = f"{chip.prefix}_{feature.label}"
                        temps[name] = {
                            'value': round(feature.get_value(), 1),
                            'max': getattr(feature, 'max', None),
                            'min': getattr(feature, 'min', None)
                        }
        except:
            pass
        return temps
    
    def get_psutil_temps(self):
        temps = {}
        try:
            temps_dict = psutil.sensors_temperatures()
            for name, entries in temps_dict.items():
                for entry in entries:
                    label = entry.label or name
                    temps[label] = {
                        'value': round(entry.current, 1),
                        'max': entry.high,
                        'min': None
                    }
        except:
            pass
        return temps
    
    def get_temperatures(self):
        """获取所有可用的温度信息"""
        all_temps = {}
        
        # 获取psutil的温度信息
        all_temps.update(self.get_psutil_temps())
        
        # 根据操作系统获取额外的温度信息
        if self.system == "Windows":
            all_temps.update(self.get_windows_temps())
        elif self.system == "Linux":
            all_temps.update(self.get_linux_temps())
        
        return all_temps
    
    def __del__(self):
        # 清理资源
        if self.system == "Linux" and self.sensors:
            self.sensors.cleanup() 