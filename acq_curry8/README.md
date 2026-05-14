# acq_curry8

## 模块简介

`acq_curry8` 用于连接 **Neuroscan Curry 8** 上位机软件，通过 TCP 协议持续接收实时 EEG 数据，并解析事件触发信息。

该模块当前仅负责：

- 建立与上位机的 TCP 通信
- 请求基础信息与通道信息
- 持续接收 EEG 数据流
- 解析事件并生成 trigger
- 打印调试信息与 EEG 数据预览

## 文件说明

```text
acq_curry8/
|-- main.py
|-- config.yaml
|-- __init__.py
|-- README.md
```

## 运行方式

```bash
python -m acq_curry8.main
```

## 配置说明

`config.yaml` 主要字段如下：

- `device.host`：Curry 8 上位机 IP 地址
- `device.port`：TCP 端口，默认 `4455`
- `device.channels`：总通道数
- `device.sample_rate`：采样率
- `device.timeout_seconds`：连接超时
- `device.reconnect_interval_seconds`：断线重连间隔
- `stream.downsample_factor`：下采样因子
- `stream.eeg_channel_indices`：保留的 EEG 通道索引
- `stream.trigger_channel_index`：trigger 通道索引，可设为 `null`

## 程序流程

1. 启动采集线程
2. 尝试连接 Curry 8 上位机
3. 请求基础信息
4. 请求通道信息
5. 循环请求流数据
6. 解析 EEG 与事件
7. 合成 `EegFrame`
8. 打印 EEG 摘要与预览

## 运行输出

程序运行后会打印：

- 连接状态
- 基础信息
- 通道信息
- 事件包内容
- EEG 帧信息
- trigger 非零位置
- EEG 数据预览

## 适用场景

- Curry 8 实时数据接收
- 上位机联调
- Trigger 事件调试
- 与 `NeuroScanSim_Curry8` 联合测试

## ⭐
- 技术交流：`liyangyang20@mails.ucacs.ac.cn`
- 别人听时，我假装讲；别人讲时，我假装听。
