# NeuroScanSim_Curry9

## 工具简介

`NeuroScanSim_Curry9` 是用于模拟 **Neuroscan Curry 9** 上位机 TCP 服务的图形化仿真工具，主要用于与 `acq_curry9` 进行系统级联调。

## 主要功能

- 配置监听 IP 与端口
- 配置通道数、采样率、每包采样点
- 选择 `float32` 或 `int16` 数据格式
- 自动发送 EEG 数据包
- 自动发送试次开始/结束事件
- 支持手动发送 trial 事件
- 支持 536 字节事件结构
- 支持 keep-alive 包模拟
- 提供连接状态颜色反馈
- 提供日志打印

## 运行方式

```bash
python NeuroScanSim_Curry9/main.py
```

## 联调方式

1. 启动 `NeuroScanSim_Curry9`
2. 点击“启动仿真 / Start Simulator”
3. 启动 `acq_curry9`
4. 观察状态是否变为“已连接 / Connected”
5. 查看日志是否出现：
   - 客户端连接
   - 基础信息发送
   - 通道信息发送
   - EEG packet 发送
   - 事件发送
   - keepalive 发送

## 适用场景

- 无真实设备时的 Curry 9 软件联调
- EEG 与事件联合调试
- Trial 切分逻辑验证
- 上层实验流程测试

## ⭐
- 技术交流：`liyangyang20@mails.ucacs.ac.cn`
- 别人听时，我假装讲；别人讲时，我假装听。

