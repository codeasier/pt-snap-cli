class EventFieldDefs:
    ID = "id"
    ACTION = "action"
    ADDR = "address"
    SIZE = "size"
    STREAM = "stream"
    ALLOCATED = "allocated"
    ACTIVE = "active"
    RESERVED = "reserved"
    CALLSTACK_ID = "callstackId"


class CallstackFieldDefs:
    ID = "id"
    CALLSTACK = "callstack"


class BlockFieldDefs:
    ID = "id"
    ADDR = "address"
    SIZE = "size"
    REQUESTED_SIZE = "requestedSize"
    STATE = "state"
    ALLOC_EVENT_ID = "allocEventId"
    FREE_EVENT_ID = "freeEventId"
