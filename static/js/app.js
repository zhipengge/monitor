// 初始化图表
function initCharts() {
    // 设置Chart.js全局样式
    Chart.defaults.color = '#e9ecef';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
    
    // CPU使用率历史图表
    const cpuCtx = document.getElementById('cpuChart');
    if (cpuCtx) {
        const cpuChart = new Chart(cpuCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU使用率 (%)',
                    data: [],
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 500
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
        
        // 内存使用率图表
        const memCtx = document.getElementById('memChart');
        if (memCtx) {
            const memChart = new Chart(memCtx.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: ['已用', '可用'],
                    datasets: [{
                        data: [
                            parseFloat(memCtx.getAttribute('data-mem-used')),
                            parseFloat(memCtx.getAttribute('data-mem-free'))
                        ],
                        backgroundColor: ['#20c997', '#253850'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '75%',
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
        
        // 更新时间显示
        function updateTime() {
            const timeElement = document.getElementById('current-time');
            if (timeElement) {
                const now = new Date();
                timeElement.textContent = now.toLocaleTimeString();
            }
        }
        setInterval(updateTime, 1000);
        updateTime();
        
        // 实时数据更新
        setInterval(async () => {
            try {
                const response = await axios.get('/api/hardware_info');
                const data = response.data;
                
                // 更新CPU图表
                const now = new Date().toLocaleTimeString();
                if (cpuChart.data.labels.length > 15) {
                    cpuChart.data.labels.shift();
                    cpuChart.data.datasets[0].data.shift();
                }
                cpuChart.data.labels.push(now);
                cpuChart.data.datasets[0].data.push(data.cpu.total_usage);
                cpuChart.update();
                
                // 更新CPU进度条
                const progressBar = document.querySelector('.progress-bar');
                if (progressBar) {
                    progressBar.style.width = data.cpu.total_usage + '%';
                    const usageSpan = progressBar.querySelector('span');
                    if (usageSpan) {
                        usageSpan.textContent = data.cpu.total_usage.toFixed(1) + '%';
                    }
                }
                
                // 更新CPU芯片UI
                if (data.cpu.usage_per_core) {
                    data.cpu.usage_per_core.forEach((usage, index) => {
                        const coreElement = document.querySelector(`.chip-core[data-core-id="${index}"]`);
                        if (coreElement) {
                            // 更新使用率
                            const usageElement = coreElement.querySelector('.core-usage');
                            if (usageElement) {
                                usageElement.textContent = usage.toFixed(1) + '%';
                            }
                            
                            // 更新核心状态类
                            coreElement.classList.remove('core-high', 'core-medium', 'core-low');
                            if (usage > 80) {
                                coreElement.classList.add('core-high');
                            } else if (usage > 50) {
                                coreElement.classList.add('core-medium');
                            } else {
                                coreElement.classList.add('core-low');
                            }
                            
                            // 添加闪烁效果
                            coreElement.classList.add('updating');
                            setTimeout(() => {
                                coreElement.classList.remove('updating');
                            }, 500);
                        }
                    });
                }
                
                // 更新温度信息
                if (data.temperatures) {
                    let coreIndex = 0;
                    for (const [key, sensor] of Object.entries(data.temperatures)) {
                        if (key.toLowerCase().includes('core') && key.toLowerCase().includes('temp')) {
                            const coreElement = document.querySelector(`.chip-core[data-core-id="${coreIndex}"]`);
                            if (coreElement) {
                                const tempElement = coreElement.querySelector('.core-temp');
                                if (tempElement) {
                                    tempElement.textContent = sensor.value + '°C';
                                    
                                    // 更新温度状态类
                                    tempElement.classList.remove('temp-high', 'temp-medium', 'temp-normal');
                                    if (sensor.value > 70) {
                                        tempElement.classList.add('temp-high');
                                    } else if (sensor.value > 60) {
                                        tempElement.classList.add('temp-medium');
                                    } else {
                                        tempElement.classList.add('temp-normal');
                                    }
                                }
                            }
                            coreIndex++;
                        }
                    }
                }
                
            } catch (error) {
                console.error('获取监控数据失败:', error);
            }
        }, 2000); // 2秒更新一次
    }
}

// 添加CSS变量设置
function setDynamicStyles() {
    // 设置doughnut-progress的百分比
    document.querySelectorAll('.doughnut-progress').forEach(el => {
        const percent = el.getAttribute('style').match(/--percent:\s*(\d+)/);
        if (percent && percent[1]) {
            el.style.background = `conic-gradient(
                var(--bs-success) 0% ${percent[1]}%,
                #e9ecef ${percent[1]}% 100%
            )`;
        }
    });
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    setDynamicStyles();
}); 