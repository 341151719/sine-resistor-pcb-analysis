# 节点描述法：全元器件接入版

## 电气节点

| 节点 | 含义 |
|---|---|
| `0` | 全局模拟地 / 喇叭负端 |
| `SPK` | 喇叭正端，也是合成阻抗端口 |
| `DRV` | OPA548 输出端，经过 `RSHUNT` 后到 `SPK` |
| `VSENSE` | INA149 差分检测输出，`V(SPK)-V(DRV)` |
| `ISIG` | OPA1656 放大 50 倍后的电流信号，约 `5*iport` |
| `DAC_R` | MCU/DAC 阻值命令，`0~3 V` |
| `VK` | 缩放/偏置后的阻值命令，`VK = Rx/10` |
| `MUL` | AD633 输出，`MUL = ISIG*VK/10` |
| `VCMD` | 后级放大 20 倍后给 OPA548 的命令，理想为 `Rx*iport` |
| `P18/N18` | OPA548 ±18 V 电源 |
| `P15/N15` | 小信号 ±15 V 电源 |
| `V3V3` | MCU/DAC 3.3 V 电源 |

## 机械/电声节点

| 节点 | 含义 |
|---|---|
| `VEL` | 膜片速度，电压值等价 `m/s` |
| `XNODE` | 膜片位移，电压值等价 `m` |
| `RTARGET` | 目标总等效电阻 `1~100 Ω` |
| `RXNODE` | 外接合成阻抗 `Rx=Rtarget-Re` |
| `REFF` | 从端口重建的总等效电阻 `Re + V(SPK)/Iport` |
| `ERR` | `REFF-RTARGET` |
| `REMNODE` | 电磁阻尼 `(Bl)^2/Rtarget` |
| `QNODE` | 估算有效机械 Q |

## 端口关系

```text
DRV ── RSHUNT ── SPK ── LVC ── RVC ── BEMF ── GND
```

端口电流定义为：

```text
iport = (V(SPK)-V(DRV))/RSHUNT
```

控制链：

```text
VSENSE = V(SPK)-V(DRV)
ISIG   = 50*VSENSE = 5*iport
VK     = Rx/10
MUL    = ISIG*VK/10 = Rx*iport/20
VCMD   = 20*MUL = Rx*iport
OPA548 drives DRV so that SPK ≈ VCMD
```

于是外接电路对端口呈现：

```text
V(SPK) ≈ Rx(t) * iport
Rtarget(t) = Re + Rx(t)
```
