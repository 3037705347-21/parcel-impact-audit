# 包裹三维冲击批次分析器

`impact_audit` 读取跌落试验台导出的三维单点碰撞事件，并生成逐事件报告。当前工作区的 `data/impact_events.csv` 是按固定规则和随机种子生成的模拟记录，用于检查程序流程，不代表现场采集。

输入包含 `mass_kg`、六个惯性张量分量、质心速度、角速度、接触点位置、挡板单位法向、恢复系数和摩擦系数。坐标采用右手系，角度单位为弧度。所有长度、速度、冲量和能量均为 SI 单位。

运行方式：

```bash
python -m impact_audit \
  --input data/impact_events.csv \
  --output out/impact_report.json
```

输出保留输入顺序，既要包含每个事件的冲量、碰后运动状态和能量账，也要包含批次汇总。工作区只依赖 Python 标准库。

托盘双角同时落地时使用另一条入口：

```bash
python -m impact_audit pair \
  --input data/pallet_landings.csv \
  --output out/pallet_report.json
```

双接触批次需要在两个法向冲量都非负的前提下处理单边接触，并在两个摩擦冲量的联合箱约束内求解。`data/pallet_landings.csv` 同样是固定种子生成的模拟记录。
