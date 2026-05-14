# NeuroScanSim_Curry8

## 工具简介

`NeuroScanSim_Curry8` 是用于模拟 **Neuroscan Curry 8** 上位机 TCP 服务的图形化仿真工具，主要用于与 `acq_curry8` 进行系统级联调。

## 主要功能

- 配置监听 IP 与端口
- 配置通道数、采样率、每包采样点
- 选择 `float32` 或 `int16` 数据格式
- 自动发送 EEG 数据
- 自动或手动注入事件码
- 响应基础信息、通道信息、开始流、停止流请求
- 提供连接状态颜色反馈
- 提供日志打印

## 运行方式

```bash
python NeuroScanSim_Curry8/main.py
```

## 联调方式

1. 启动 `NeuroScanSim_Curry8`
2. 点击“启动仿真 / Start Simulator”
3. 启动 `acq_curry8`
4. 观察界面右侧状态是否变为“已连接 / Connected”
5. 查看日志是否出现：
   - 客户端连接
   - 基础信息发送
   - 通道信息发送
   - EEG 数据发送
   - 事件发送

## 适用场景

- 无真实设备时的 Curry 8 软件联调
- 协议验证
- 事件触发调试
- 上层采集程序测试

## ⭐
- 技术交流：`liyangyang20@mails.ucacs.ac.cn`
- 别人听时，我假装讲；别人讲时，我假装听。

