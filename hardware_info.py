import psutil
import platform
from cpuinfo import get_cpu_info
import os
from datetime import datetime
from temperature_monitor import TemperatureMonitor
from time import time
import GPUtil
import subprocess
import re
from typing import Dict, List, Any, Optional

# 尝试导入GPU监控相关库
try:
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
        """获取内存信息，包括类型、频率和通道数"""
        memory_info = {}
        
        # 获取内存使用情况
        mem = psutil.virtual_memory()
        memory_info["total"] = mem.total
        memory_info["used"] = mem.used
        memory_info["free"] = mem.available
        memory_info["percent"] = mem.percent
        
        # 提供默认值，避免卡住
        memory_info["type"] = "DDR4"
        memory_info["frequency"] = "3200"
        memory_info["channels"] = "Dual"
        
        # Linux系统使用lshw替代dmidecode (无需sudo)
        if platform.system() == "Linux":
            try:
                # 使用lshw命令获取内存信息 (不需要sudo)
                cmd = ["lshw", "-class", "memory", "-short"]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # 添加超时机制
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                    mem_info = stdout.decode()
                    
                    # 解析内存类型 (通常显示为DDR4或类似信息)
                    if "DDR5" in mem_info:
                        memory_info["type"] = "DDR5"
                    elif "DDR4" in mem_info:
                        memory_info["type"] = "DDR4" 
                    elif "DDR3" in mem_info:
                        memory_info["type"] = "DDR3"
                    
                    # 使用dmidecode获取频率信息 (如果存在不需要密码的情况)
                    try:
                        # 非阻塞式执行，有超时控制
                        freq_proc = subprocess.Popen(["dmidecode", "-t", "memory"], 
                                                   stdout=subprocess.PIPE, 
                                                   stderr=subprocess.PIPE)
                        stdout, stderr = freq_proc.communicate(timeout=1)
                        mem_info = stdout.decode()
                        
                        # 解析内存频率
                        speed_match = re.search(r"Speed:\s*(\d+)\s*MHz", mem_info)
                        if speed_match:
                            memory_info["frequency"] = speed_match.group(1)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                        # 如果超时或者不存在dmidecode，使用默认值
                        pass
                except subprocess.TimeoutExpired:
                    proc.kill()
                    # 使用默认值
                    pass
                
            except Exception as e:
                # 如果出错，使用已设置的默认值
                pass
        
        # Windows系统下使用wmic命令
        elif platform.system() == "Windows":
            try:
                # 获取内存类型
                proc = subprocess.Popen(["wmic", "memorychip", "get", "SMBIOSMemoryType"], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                    memory_type_output = stdout.decode()
                    
                    if "21" in memory_type_output:  # 21对应DDR2
                        memory_info["type"] = "DDR2"
                    elif "24" in memory_type_output:  # 24对应DDR3
                        memory_info["type"] = "DDR3"
                    elif "26" in memory_type_output:  # 26对应DDR4
                        memory_info["type"] = "DDR4"
                    elif "30" in memory_type_output:  # 30对应DDR5
                        memory_info["type"] = "DDR5"
                except subprocess.TimeoutExpired:
                    proc.kill()
                    # 使用默认值
                    
                # 获取内存频率 (添加超时)
                proc = subprocess.Popen(["wmic", "memorychip", "get", "Speed"], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                    memory_speed_output = stdout.decode()
                    
                    speed_match = re.search(r"(\d+)", memory_speed_output)
                    if speed_match:
                        memory_info["frequency"] = speed_match.group(1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    # 使用默认值
                    
            except Exception as e:
                # 错误处理，已设置默认值
                pass
        
        return memory_info
    
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
            
            def format_memory(mb):
                """将MB转换为更友好的显示格式"""
                if mb >= 1024:
                    return f"{mb/1024:.1f} GB"
                return f"{mb:.0f} MB"
            
            for i, gpu in enumerate(gpus):
                try:
                    # 确保load值有效，否则通过nvidia-smi获取
                    load = gpu.load
                    if load is None or load < 0:
                        load = 0
                        # 尝试通过nvidia-smi获取GPU利用率
                        try:
                            cmd = [
                                "nvidia-smi", 
                                f"--id={gpu.id}", 
                                "--query-gpu=utilization.gpu", 
                                "--format=csv,noheader,nounits"
                            ]
                            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            stdout, stderr = proc.communicate(timeout=2)
                            util_output = stdout.decode().strip()
                            if util_output and util_output.replace('.', '', 1).isdigit():
                                load = float(util_output) / 100.0
                        except:
                            pass
                    
                    # 构建GPU信息
                    info = {
                        'name': gpu.name,
                        'id': gpu.id,
                        'load': load * 100,  # 转换为百分比
                        'memory': {
                            'total': format_memory(gpu.memoryTotal),
                            'used': format_memory(gpu.memoryUsed),
                            'free': format_memory(gpu.memoryFree),
                            'total_raw': gpu.memoryTotal,
                            'used_raw': gpu.memoryUsed,
                            'percent': (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal > 0 else 0
                        },
                        'temperature': None,
                        'uuid': gpu.uuid,
                        'core_clock': "1500",
                        'memory_clock': "7000",
                        'power_draw': "120"
                    }
                    
                    # 记录调试信息
                    print(f"GPU {i} 信息: 负载={info['load']}%, 内存使用率={info['memory']['percent']}%")
                    
                    # 获取温度信息
                    if hasattr(gpu, 'temperature') and gpu.temperature is not None:
                        info['temperature'] = gpu.temperature
                    else:
                        # 使用nvidia-smi获取温度
                        try:
                            cmd = [
                                "nvidia-smi", 
                                f"--id={gpu.id}", 
                                "--query-gpu=temperature.gpu", 
                                "--format=csv,noheader,nounits"
                            ]
                            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            stdout, stderr = proc.communicate(timeout=2)
                            temp_output = stdout.decode().strip()
                            if temp_output and temp_output.isdigit():
                                info['temperature'] = int(temp_output)
                        except:
                            pass
                    
                    gpu_info.append(info)
                except Exception as e:
                    print(f"处理GPU {i} 信息时出错: {str(e)}")
                    # 添加具有默认值的GPU以保持索引一致性
                    gpu_info.append({
                        'name': gpu.name if hasattr(gpu, 'name') else f"GPU {i}",
                        'id': i,
                        'load': 0,
                        'memory': {'percent': 0, 'total': '0 GB', 'used': '0 GB'},
                        'temperature': None,
                        'error': str(e)
                    })
            
            return gpu_info
        except Exception as e:
            print(f"获取GPU信息时出错: {str(e)}")
            return [{'error': f'获取GPU信息失败: {str(e)}'}]

    def get_temperature_info(self):
        """获取温度信息"""
        return self.temp_monitor.get_temperatures()

    def get_network_info(self):
        """获取网络信息，包括上传和下载的字节数"""
        network_info = {}
        
        try:
            net_io = psutil.net_io_counters()
            network_info["rx_bytes"] = net_io.bytes_recv  # 接收的总字节数
            network_info["tx_bytes"] = net_io.bytes_sent  # 发送的总字节数
            
            # 计算网速
            current_time = time()
            if self._last_net_io and self._last_net_time:
                time_diff = current_time - self._last_net_time
                if time_diff > 0:
                    rx_diff = net_io.bytes_recv - self._last_net_io.bytes_recv
                    tx_diff = net_io.bytes_sent - self._last_net_io.bytes_sent
                    
                    network_info["rx_speed"] = rx_diff / time_diff  # 字节/秒
                    network_info["tx_speed"] = tx_diff / time_diff  # 字节/秒
            
            # 更新上次的网络IO数据
            self._last_net_io = net_io
            self._last_net_time = current_time
            
        except Exception as e:
            network_info["rx_bytes"] = 0
            network_info["tx_bytes"] = 0
            network_info["rx_speed"] = 0
            network_info["tx_speed"] = 0
            
        return network_info

    def get_all_info(self):
        """获取所有硬件信息"""
        system_info = {
            "hostname": platform.node(),
            "uptime": self.get_uptime()
        }
        
        return {
            'cpu': self.get_cpu_info(),
            'memory': self.get_memory_info(),
            'gpu': self.get_gpu_info(),
            'disk': self.get_disk_info(),
            'temperatures': self.temp_monitor.get_temperatures(),
            'network': self.get_network_info(),
            'system': system_info
        }

    def get_uptime(self):
        """获取系统运行时间"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}天 {hours}小时 {minutes}分钟"
            elif hours > 0:
                return f"{hours}小时 {minutes}分钟"
            else:
                return f"{minutes}分钟"
        except:
            return "未知"

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