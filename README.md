# PyNeuroscan_NetStream

## 项目简介

`PyNeuroscan_NetStream` 用于对接 **Neuroscan Curry** 上位机软件的 TCP 实时数据流，完成脑电数据接收、事件解析、试次切分与系统级联调。

当前仓库包含两类程序：

- `acq_curry8`：用于接收 Curry 8 连续 EEG 数据
- `acq_curry9`：用于接收 Curry 9 连续 EEG 与事件数据，并进行试次切分
- `NeuroScanSim_Curry8`：Curry 8 上位机仿真工具
- `NeuroScanSim_Curry9`：Curry 9 上位机仿真工具

## 目录结构

```text
PyNeuroscan_NetStream/
|-- acq_curry8/
|-- acq_curry9/
|-- NeuroScanSim_Curry8/
|-- NeuroScanSim_Curry9/
|-- README.md
```

## 功能概览

### 1. acq_curry8

- 连接 Curry 8 上位机 TCP 服务
- 请求基础信息与通道信息
- 持续接收 EEG 数据包
- 解析事件并写入 trigger
- 支持下采样与通道选择
- 控制台打印连接状态、事件信息和 EEG 数据预览

### 2. acq_curry9

- 连接 Curry 9 上位机 TCP 服务
- 请求基础信息与通道信息
- 持续接收 EEG、事件与 keep-alive 数据
- 根据事件码 `16` / `20` 进行 trial 切分
- 控制台打印连接状态、数据包信息、EEG 数据预览和 trial 信息

### 3. NeuroScanSim_Curry8 / NeuroScanSim_Curry9

- 提供 PyQt5 图形界面
- 可配置监听 IP、端口、采样率、通道数、数据类型等参数
- 可模拟基础信息、通道信息、EEG 数据、事件数据
- 支持系统级联调
- 提供连接状态颜色反馈与日志显示

## 运行方式

### 启动 Curry 8 数据接收

```bash
python -m acq_curry8.main
```
！[gui](./imgs/acq_eeg.png)
### 启动 Curry 9 数据接收

```bash
python -m acq_curry9.main
```

### 启动 Curry 8 仿真器

```bash
python NeuroScanSim_Curry8/main.py
```
！[gui](./imgs/sys_sim.png)
### 启动 Curry 9 仿真器

```bash
python NeuroScanSim_Curry9/main.py
```

## 通信协议说明

两套采集程序均基于 Curry TCP 二进制协议，核心请求码如下：

| 请求码 | 含义 |
|---|---|
| `3` | 请求通道信息 |
| `6` | 请求基础信息 |
| `8` | 请求开始/继续流数据 |
| `9` | 请求停止流数据 |

协议头固定为 20 字节：

- `CTRL`
- `code`
- `request`
- `start_sample`
- `body_size`
- `uncompressed_size`

## 联调建议

### Curry 8 联调

1. 先启动 `NeuroScanSim_Curry8`
2. 再启动 `acq_curry8`
3. 观察仿真器日志中是否出现客户端连接
4. 观察 `acq_curry8` 控制台是否打印：
   - `basic info`
   - `channel info`
   - `event packet`
   - `EEG frame`

### Curry 9 联调

1. 先启动 `NeuroScanSim_Curry9`
2. 再启动 `acq_curry9`
3. 观察仿真器日志中是否出现：
   - `EEG packet #... sent`
   - `event sent`
4. 观察 `acq_curry9` 控制台是否打印：
   - `packet #... received`
   - `EEG block`
   - `event`
   - `trial built`

## 依赖环境

- Python 3.10 及以上
- `numpy`
- `pyyaml`
- `PyQt5`

## ⭐
- 技术交流：`liyangyang20@mails.ucacs.ac.cn`
- 别人听时，我假装讲；别人讲时，我假装听。
