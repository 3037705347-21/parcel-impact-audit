# 三维仪器箱冲击复核

包装实验室的跌落试验台开始同时记录箱体姿态、角速度和角部接触位置。工程师要据此判断箱体撞上固定挡板后会不会发生二次翻转，以及角部摩擦是否已经进入滑移。请补全 `/workspace/impact_audit` 中的分析程序，输出一份能逐事件复核的三维碰撞报告。

工作区里的 `data/impact_events.csv` 是按固定种子生成的模拟批次，不是现场实测数据。程序只能使用 Python 标准库，输入输出统一使用米、千克、秒、牛顿、焦耳和弧度。

## 输入

CSV 必须包含以下列，允许额外列，事件按文件中的先后顺序处理：

```text
event_id,mass_kg,ixx,iyy,izz,ixy,ixz,iyz,
vx,vy,vz,wx,wy,wz,rx,ry,rz,nx,ny,nz,
restitution,friction_coefficient
```

`m` 为质量。关于质心的对称惯性张量为：

```text
I = [[ixx, ixy, ixz],
     [ixy, iyy, iyz],
     [ixz, iyz, izz]]
```

`v=(vx,vy,vz)` 是碰前质心速度，`w=(wx,wy,wz)` 是角速度，`r=(rx,ry,rz)` 是接触点相对质心的位置，`n=(nx,ny,nz)` 是挡板指向箱体的单位法向。`restitution` 在 `[0,1]` 内，`friction_coefficient` 不得小于零。

采用瞬时单点碰撞。令 `C(r)` 表示矩阵形式的叉乘，`C(r)q=r×q`，令 `W=I^-1`。接触点速度与接触空间逆质量矩阵为：

```text
vc = v + w×r
K  = 1/m * Identity(3) - C(r) W C(r)
```

## 求解顺序

1. 按碰前 `vc` 求法向冲量：

```text
J_n = -(1 + restitution) * dot(vc,n) / dot(n, K n)
J_normal = J_n * n
```

2. 施加 `J_normal`，更新 `v += J_normal/m`、`w += W(r×J_normal)`，再重算一次接触点速度 `vc`。

3. 取切向部分 `vt=vc-dot(vc,n)n`。在垂直于 `n` 的平面内选择任意右手正交基 `t1,t2`，求二维矩阵 `M` 和右端向量 `q`：

```text
M_ij = dot(t_i, K t_j)
q_i  = -dot(t_i, vt)
```

先求粘着候选 `a=M^-1 q` 及 `Jt_need=a1*t1+a2*t2`。若 `|Jt_need| <= friction_coefficient*J_n`，取 `J_t=Jt_need`，接触状态为 `stick`。否则取 `J_t=-friction_coefficient*J_n*vt/|vt|`，状态为 `slide`。这里采用先法向、再切向的顺序冲量模型，不再用摩擦结果回头修正法向冲量。

4. 再施加 `J_t`，更新速度和角速度。总碰后状态为：

```text
v_after = v + J_t/m
w_after = w + W(r×J_t)
```

其中第二步后的 `v`、`w` 作为这一步的初值。碰前、碰后能量按 `0.5*m*|v|^2 + 0.5*dot(w,I w)` 计算，能量损失为碰前减碰后。

## 命令与输出

完成后的入口必须继续支持：

```bash
python -m impact_audit \
  --input data/impact_events.csv \
  --output out/impact_report.json
```

输出为 UTF-8 JSON，顶层只有 `events` 和 `summary`。`events` 与输入顺序一致，每项结构如下：

```json
{
  "event_id": "IMP-001",
  "normal_impulse_ns": 12.3,
  "tangential_impulse_ns": {"x": -0.4, "y": 0.2, "z": -1.1},
  "contact_mode": "slide",
  "velocity_after_m_s": {"x": 0.4, "y": -0.7, "z": 0.1},
  "angular_velocity_after_rad_s": {"x": 1.3, "y": -0.2, "z": 0.8},
  "kinetic_energy_before_j": 4.2,
  "kinetic_energy_after_j": 3.1,
  "energy_loss_j": 1.1
}
```

`summary` 必须包含：

```json
{
  "event_count": 12,
  "stick_count": 6,
  "slide_count": 6,
  "total_energy_loss_j": 14.6,
  "maximum_energy_gain_j": 0.0
}
```

`maximum_energy_gain_j` 取逐事件 `-energy_loss_j` 与零之间的较大者。数值直接按双精度输出，不要求固定小数位。

## 输入验收

缺列、空批次、空事件编号、任一数值不是有限数、质量不为正、惯性张量不是正定矩阵、恢复系数越界、摩擦系数为负、法向模长偏离 1 超过 `1e-9`，或者碰前接触点没有朝挡板运动时，命令必须以非零状态退出。非法批次不能创建输出文件，也不能改动已经存在的输出文件。目标 JSON 必须在全部事件成功求解后整体原子替换，不能留下截断内容。

## 双接触托盘批次

托盘落下时常常是两个角同时接触地面。这个场景不能再把两个接触点当成互不相关的单点事件，程序还要支持：

```bash
python -m impact_audit pair \
  --input data/pallet_landings.csv \
  --output out/pallet_report.json
```

双接触 CSV 的列固定为：

```text
event_id,mass_kg,inertia_kg_m2,vx_m_s,vy_m_s,omega_rad_s,
r1x_m,r1y_m,r2x_m,r2y_m,nx,ny,restitution,friction_coefficient
```

箱体是二维刚体，`I` 为绕质心的标量转动惯量。两个接触点共用单位法向 `n`，切向取 `t=(-ny,nx)`。令 `K_dd[i][j]=1/m+(r_i×d)(r_j×d)/I`，其中 `d` 依次取 `n` 和 `t`，得到 2×2 的 `K_nn`、`K_tt`。

碰前接触点法向速度为 `a_i=dot(v+omega×r_i,n)`。要求至少一个 `a_i<0`。有效接触集必须满足：

```text
J_i >= 0
K_nn[S,S] * J_S = -(1+restitution) * a_S
非有效接触碰后的法向速度 >= 0
有效接触碰后法向速度 = -restitution * a_i
```

对大小为 1 或 2 的接近接触子集逐一求解上面的方程，保留所有冲量非负且非有效接触没有继续穿透的候选。若出现多个候选，取法向冲量总和最小的一组。

施加法向冲量后，在有效接触上求切向冲量 `q_i`。令 `v_t` 为这组接触的碰后切向速度，求：

```text
minimize  0.5*q^T*K_tt*q + v_t^T*q
subject to  -friction_coefficient*J_i <= q_i <= friction_coefficient*J_i
```

有效接触数最多为 2。对每个分量枚举自由、位于下界、位于上界三种状态；固定分量取边界，自由分量解线性方程，再检查边界最优性。若最优 `q_i` 位于边界，接触状态记为 `slide`；位于内部记为 `stick`。法向冲量为零的接触记为 `inactive`。

双接触事件输出结构：

```json
{
  "event_id": "LAND-001",
  "contact_normal_impulses_ns": [5.2, 2.7],
  "contact_tangent_impulses_ns": [
    {"x": -0.1, "y": 0.8},
    {"x": 0.0, "y": 0.6}
  ],
  "contact_modes": ["stick", "slide"],
  "velocity_after_m_s": {"x": 0.2, "y": 0.4},
  "angular_velocity_after_rad_s": -0.3,
  "kinetic_energy_before_j": 9.1,
  "kinetic_energy_after_j": 3.4,
  "energy_loss_j": 5.7
}
```

`summary` 中的 `event_count` 统计事件数，`stick_count`、`slide_count`、`inactive_count` 统计所有事件的两个接触模式，能量字段定义与单点批次相同。双接触输入同样要求缺列、空批次、空编号、非有限数、非正质量或惯量、系数越界、非法法向、两个接触点重合或没有任何接近接触时非零退出，并且不能创建或覆盖目标 JSON。
