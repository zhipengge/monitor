import psutil
import platform
from cpuinfo import get_cpu_info
import os
from datetime import datetime
from temperature_monitor import TemperatureMonitor
from time import time

# 尝试导入GPU监控相关库
try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError as e:
    print(f"GPU监控初始化错误(ImportError): {str(e)}")
    GPU_AVAILABLE = False
except Exception as e:
    print(f"GPU监控初始化错误: {str(e)}")
    GPU_AVAILABLE = False

class HardwareInfo:
    def __init__(self):
        self.temp_monitor = TemperatureMonitor()
        self._last_net_io = None
        self._last_net_time = None

    def _format_gpu_memory(self, mb_value):
        """将MB转换为更友好的显示格式"""
        if mb_value > 1024:
            return f"{mb_value/1024:.1f} GB"
        return f"{mb_value:.0f} MB"

    @staticmethod
    def get_cpu_info():
        try:
            cpu_info = get_cpu_info()
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            cpu_freq = psutil.cpu_freq(percpu=False)
            
            info = {
                'name': cpu_info.get('brand_raw', 'Unknown CPU'),
                'cores': psutil.cpu_count(),
                'physical_cores': psutil.cpu_count(logical=False),
                'usage_per_core': cpu_percent,
                'total_usage': sum(cpu_percent) / len(cpu_percent),
            }
            
            # 添加CPU频率信息（如果可用）
            if cpu_freq:
                info.update({
                    'current_freq': round(cpu_freq.current, 2),
                    'min_freq': round(cpu_freq.min, 2),
                    'max_freq': round(cpu_freq.max, 2)
                })
            
            return info
        except Exception as e:
            return {
                'name': 'Unknown CPU',
                'cores': psutil.cpu_count() or 0,
                'physical_cores': psutil.cpu_count(logical=False) or 0,
                'usage_per_core': [0],
                'total_usage': 0,
                'error': str(e)
            }
    
    @staticmethod
    def get_memory_info():
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent,
                'swap_total': swap.total,
                'swap_used': swap.used,
                'swap_free': swap.free,
                'swap_percent': swap.percent
            }
        except Exception as e:
            return {
                'error': str(e)
            }
    
    @staticmethod
    def get_disk_info():
        disks = []
        try:
            for partition in psutil.disk_partitions(all=False):
                # 跳过CD-ROM等特殊设备（Windows系统）
                if platform.system() == "Windows" and "cdrom" in partition.opts.lower():
                    continue
                    
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info = {
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'filesystem': partition.fstype,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                    
                    # 在Linux/Mac系统上尝试获取磁盘IO统计
                    if platform.system() != "Windows":
                        try:
                            disk_io = psutil.disk_io_counters(perdisk=True)
                            device_name = os.path.basename(partition.device)
                            if device_name in disk_io:
                                io_info = disk_io[device_name]
                                disk_info.update({
                                    'read_bytes': io_info.read_bytes,
                                    'write_bytes': io_info.write_bytes
                                })
                        except:
                            pass
                            
                    disks.append(disk_info)
                except:
                    continue
        except Exception as e:
            return [{'error': str(e)}]
        return disks
    
    def get_system_info(self):
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
            
            info = {
                'os': f"{platform.system()} {platform.release()}",
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'boot_time': boot_time,
                'network_speed': self._get_network_speed(),
            }
            
            # 获取网络接口信息
            try:
                network = psutil.net_if_addrs()
                net_info = {}
                for interface, addresses in network.items():
                    net_info[interface] = [str(addr.address) for addr in addresses if addr.family.name in ('AF_INET', 'AF_INET6')]
                info['network_interfaces'] = net_info
            except:
                pass
                
            return info
        except Exception as e:
            return {
                'error': str(e)
            }

    @staticmethod
    def get_gpu_info():
        if not GPU_AVAILABLE:
            return [{'error': 'GPU监控未启用或未安装GPUtil'}]
        
        try:
            gpus = GPUtil.getGPUs()
            gpu_info = []
            
            for gpu in gpus:
                def format_memory(mb):
                    """将MB转换为更友好的显示格式"""
                    if mb >= 1024:
                        return f"{mb/1024:.1f} GB"
                    return f"{mb:.0f} MB"
                
                info = {
                    'name': gpu.name,
                    'id': gpu.id,
                    'load': gpu.load * 100 if gpu.load is not None else 0,  # 转换为百分比
                    'memory': {
                        'total': format_memory(gpu.memoryTotal),
                        'used': format_memory(gpu.memoryUsed),
                        'free': format_memory(gpu.memoryFree),
                        'total_raw': gpu.memoryTotal,  # 保留原始值用于计算百分比
                        'used_raw': gpu.memoryUsed,
                        'percent': (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal > 0 else 0
                    },
                    'temperature': gpu.temperature if hasattr(gpu, 'temperature') else None,  # °C
                    'uuid': gpu.uuid
                }
                gpu_info.append(info)
            
            if not gpu_info:
                return [{'error': '未检测到GPU设备'}]
            
            return gpu_info
        except Exception as e:
            print(f"获取GPU信息时出错: {str(e)}")
            return [{'error': f'获取GPU信息失败: {str(e)}'}]

    def get_temperature_info(self):
        """获取温度信息"""
        return self.temp_monitor.get_temperatures()

    def get_all_info(self):
        return {
            'cpu': self.get_cpu_info(),
            'memory': self.get_memory_info(),
            'disk': self.get_disk_info(),
            'system': self.get_system_info(),
            'gpu': self.get_gpu_info(),
            'temperatures': self.get_temperature_info()  # 添加温度信息
        }

    def _get_network_speed(self):
        """获取网络速度"""
        current_net_io = psutil.net_io_counters()
        current_time = time()
        
        if self._last_net_io is None or self._last_net_time is None:
            self._last_net_io = current_net_io
            self._last_net_time = current_time
            return {
                'upload': 0,
                'download': 0
            }
        
        time_elapsed = current_time - self._last_net_time
        
        # 计算速度（bytes/s）
        upload_speed = (current_net_io.bytes_sent - self._last_net_io.bytes_sent) / time_elapsed
        download_speed = (current_net_io.bytes_recv - self._last_net_io.bytes_recv) / time_elapsed
        
        # 更新上次的值
        self._last_net_io = current_net_io
        self._last_net_time = current_time
        
        return {
            'upload': upload_speed,
            'download': download_speed
        } 