# 拆分快照

[English](../en/splitting.md) | 中文

`pt-snap split` 将 PyTorch 原始内存快照拆成更小的文件。每个文件都能还原切片边界处
的分配器状态，并独立回放自己的事件范围。该命令不会直接截断事件数组，不会读取或修改
focus，也不会生成 SnapshotDB。如需使用 SQLite 查询，请单独导入生成的 pickle 切片。

> **安全警告：** 只能使用可信的 pickle 输入。反序列化源快照或任意 pickle 切片都可能
> 执行任意代码；`pt-snap split` 不是沙箱。

## 命令契约

```bash
pt-snap split SNAPSHOT_PATH \
  --output OUTPUT_DIRECTORY \
  [--device DEVICE_ID] \
  (--slices COUNT | --max-entries COUNT) \
  [--format pickle|json]
```

源文件必须是已存在的普通 `.pkl` 或 `.pickle` 文件。`--output` 必须提供；其父目录必须
已经存在，而输出路径本身不能以文件、目录或符号链接形式存在。拆分绝不会合并或覆盖已有目标。

以下策略必须且只能选择一种：

| 参数 | 含义 |
| --- | --- |
| `--slices COUNT` | 为每个选中设备请求正数个切片 |
| `--max-entries COUNT` | 将每个切片的最大事件数限制为正数 `COUNT` |

`--format` 只接受 `pickle` 或 `json`，默认值为 `pickle`。

## 设备与命名

指定 `--device ID` 时，只拆分该非空设备。省略 `--device` 时，会选择所有包含追踪事件的
设备，并对每个设备独立应用同一策略；全设备模式会跳过空设备。如果所有设备都没有事件，
或显式指定的设备不存在或为空，命令会失败，不会发布空目录。

每个输出文件只包含一个设备的事件，并使用以下确定性名称：

```text
<source-stem>__device-<id>__slice-<index>.<ext>
```

切片索引从 0 开始。pickle 的扩展名为 `pkl`，JSON 的扩展名为 `json`。输入和选项相同
时，输出名称及其顺序保持相同。

示例：

```bash
# 将所有非空设备分别拆成四片
pt-snap split snapshot.pkl --slices 4 --output snapshot-slices

# 只拆分设备 1，每个规范化 JSON 文件最多包含 50000 个事件
pt-snap split snapshot.pkl --device 1 --max-entries 50000 \
  --format json --output snapshot-json
```

## Pickle 与 JSON

- `pickle` 是完整、与运行时耦合的表示，也是 `pt-snap import` 接受的格式。它保留
  Python 特有的值，但必须作为可执行的可信输入处理。
- `json` 是便于检查和交换的规范化紧凑 UTF-8 表示。它保留回放所需的值和事件顺序，
  但 `pt-snap import` 不接受 JSON；后续要生成 SnapshotDB 时应选择 pickle。

发布前，pt-snap 会加载并回放两种格式的每个切片，验证其能够重建边界状态并处理对应
事件范围。该验证不会让不可信的 pickle 变得安全。

## 发布与错误阶段

拆分会先验证参数、源与输出路径、格式、策略和设备选择，不会提前发布任何内容。生成文件
先写入输出父目录下唯一的隐藏同级暂存目录，因此暂存目录和目标目录位于同一文件系统。
所有文件加载并回放成功后，pt-snap 才使用禁止替换的原子目录重命名，将整个暂存目录发布
为 `--output`。

失败信息会标明 argument、path、conflict、device、load/engine、generated-validation
或 publication 阶段。任何失败都只清理本次创建的暂存目录，不留下部分目标目录。如果其他
进程在执行期间创建了目标路径，发布会失败，不替换也不合并该路径，并清理自有暂存输出。

成功生成 pickle 切片后，可按常规方式导入并查询其中一个切片：

```bash
pt-snap import snapshot-slices/snapshot__device-0__slice-0.pkl --no-focus
pt-snap query snapshot-slices/snapshot__device-0__slice-0.pkl.db \
  --device 0 --template-use memory_peak
```
