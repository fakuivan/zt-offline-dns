#!/usr/bin/env python3.9
from typing import Callable, TypeVar, Iterable, Set, Any, Type, Dict, Iterator, Protocol
from typing_json import from_json_obj
from queue import Queue, Empty as QueueEmpty

T = TypeVar("T")
def only_contains(seq: Iterable[T], allowed: Set[T]) -> bool:
    return set(seq) <= allowed

T = TypeVar("T")
def casted_from_json_obj(obj: Any, t: Type[T]) -> T:
    return from_json_obj(obj, t)

K = TypeVar("K")
V = TypeVar("V")
def unpack_exactly(dict_: Dict[K, V], *keys: K) -> Iterator[V]:
    if not only_contains(dict_.keys(), set(keys)):
        raise KeyError(f"Dictionary must contain keys {set(keys)} exactly")
    return unpack(dict_, *keys)

# Python typing is so stupid
cv_V = TypeVar('cv_V', covariant=True)
co_K = TypeVar('co_K', contravariant=True)
class Indexable(Protocol[co_K, cv_V]):
    def __getitem__(self, k: co_K) -> cv_V: ...

K = TypeVar("K")
V = TypeVar("V")
def unpack(mapping: Indexable[K, V], *keys: K) -> Iterator[V]:
    return (mapping[k] for k in keys)

T = TypeVar('T')
V = TypeVar('V')
def feeder(consumer: Callable[[Iterable[T]], Iterator[V]]) -> Callable[[T], V]:
    queue: Queue[T] = Queue()
    iterable = consumer(item for item in queue_iter(queue))
    def push(*elements: T) -> V:
        for item in elements:
            queue.put(item)
        return next(iterable)
    return push

T = TypeVar('T')
def queue_iter(queue: Queue[T]) -> Iterator[T]:
    while True:
        try:
            yield queue.get_nowait()
        except QueueEmpty:
            break
