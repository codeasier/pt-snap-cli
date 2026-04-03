# trace_entry_{device} 表约束
## id约束
### id >= 0场景
- 事件id升序严格按照**启动内存快照采集后的**发生顺序递增，且唯一。

### ** id < 0场景 **
- 事件id为负数时，为从原始pickle数据中虚拟生成的事件，且事件类型一定为segment_map或segment_alloc，用于还原**启动内存快照采集时刻**已有的Segment。

# block_{device} 表约束
## id约束
### id >= 0场景
- block.id如果为非负数，则与其allocEventId一定一致，共同指向了trace_entry中id相同的分配事件。

### id < 0场景
- 代表仅仅（通过原始pickle数据中的Segment信息）得知这个内存块在采集开始时就已被分配，及它从快照采集开始时的状态，而无从得知这个内存块是在何时被分配的。

- block.id为负数时，其具体值为多少无实际含义，仅用于在block表中唯一标识该内存块。

## state约束
- block.state仅在block.id为负数时才会被使用，否则无实际意义。

## requestedSize约束
- block.requestedSize与block.size的区别在于，block.requestedSize是请求的大小，而block.size是实际分配的大小（含对齐开销）。具体计算为size = math.ceil((requestedSize + 32) / 512) * 512
