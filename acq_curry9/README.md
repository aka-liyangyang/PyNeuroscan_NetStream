# acq_curry9

## 模块简介

`acq_curry9` 用于连接 **Neuroscan Curry 9** 上位机软件，通过 TCP 协议接收 EEG 数据与事件数据，并基于事件码进行 trial 切分。

该模块当前仅负责：

- 建立与 Curry 9 上位机的 TCP 通信
- 请求基础信息与通道信息
- 持续接收 EEG、事件和 keep-alive 数据
- 根据事件码 `16` / `20` 切分试次
- 打印 EEG、事件和 trial 调试信息

## 文件说明

```text
acq_curry9/
|-- main.py
|-- config.yaml
|-- __init__.py
|-- README.md
```

## 运行方式

```bash
python -m acq_curry9.main
```

## 配置说明

`config.yaml` 主要字段如下：

- `device.host`：Curry 9 上位机 IP 地址
- `device.port`：TCP 端口，默认 `4455`
- `device.channels`：总通道数
- `device.sample_rate`：采样率
- `device.timeout_seconds`：连接超时
- `device.reconnect_interval_seconds`：断线重连间隔
- `device.eeg_channel_indices`：保留的 EEG 通道索引
- `stream.trial_prefix_seconds`：trial 起始前保留的预刺激时间
- `stream.ring_buffer_seconds`：环形缓冲区长度

## 程序流程

1. 启动主循环
2. 尝试连接 Curry 9 上位机
3. 请求基础信息
4. 请求通道信息
5. 循环接收数据包
6. 解析 EEG block
7. 解析 event block
8. 将 EEG 写入环形缓冲区
9. 根据 `16 -> 20` 事件切分 trial
10. 打印数据包、EEG、事件与 trial 信息

## 事件说明

- `16`：trial 开始
- `20`：trial 结束

trial 输出形状为：

```text
(n_eeg_channels + 1, n_samples)
```

最后一行为 trigger 通道。

## 运行输出

程序运行后会打印：

- 连接状态
- 基础信息
- 通道信息
- 数据包编号与包类型
- EEG block 预览
- 事件内容
- trial 构建结果

## 适用场景

- Curry 9 实时采集联调
- 事件驱动实验调试
- Trial 切分验证
- 与 `NeuroScanSim_Curry9` 联合测试

## ⭐
- 技术交流：`liyangyang20@mails.ucacs.ac.cn`
- 别人听时，我假装讲；别人讲时，我假装听。

