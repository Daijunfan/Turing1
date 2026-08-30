from __future__ import annotations

from functools import lru_cache
from itertools import product
from typing import Iterable

from .relations import Relation


OPERATIONS: tuple[tuple[int, int], ...] = tuple(
    (arity, code)
    for arity, count in ((1, 4), (2, 16), (3, 256))
    for code in range(count)
)
OPERATION_INDEX = {operation: index for index, operation in enumerate(OPERATIONS)}
ALL_OPERATION_MASK = (1 << len(OPERATIONS)) - 1


def operation_value(arity: int, code: int, arguments: tuple[int, ...]) -> int:
    if len(arguments) != arity:
        raise ValueError("operation argument arity mismatch")
    index = sum((value & 1) << position for position, value in enumerate(arguments))
    return (code >> index) & 1


def _majority_code() -> int:
    return sum(1 << bits for bits in range(8) if bits.bit_count() >= 2)


def _minority_code() -> int:
    return sum(1 << bits for bits in range(8) if bits.bit_count() & 1)


NAMED_OPERATION_CODES = {
    "constant_0": (1, 0),
    "constant_1": (1, 3),
    "and": (2, 8),
    "or": (2, 14),
    "majority": (3, _majority_code()),
    "minority": (3, _minority_code()),
}
NAMED_WITNESSES = {
    name: 1 << OPERATION_INDEX[operation] for name, operation in NAMED_OPERATION_CODES.items()
}


@lru_cache(maxsize=None)
def _signature(arity: int, relation_mask: int) -> int:
    allowed = tuple(bits for bits in range(1 << arity) if (relation_mask >> bits) & 1)
    signature = 0
    for operation_index, (operation_arity, code) in enumerate(OPERATIONS):
        preserves = True
        for inputs in product(allowed, repeat=operation_arity):
            output = 0
            for coordinate in range(arity):
                arguments = tuple((item >> coordinate) & 1 for item in inputs)
                output |= operation_value(operation_arity, code, arguments) << coordinate
            if not ((relation_mask >> output) & 1):
                preserves = False
                break
        if preserves:
            signature |= 1 << operation_index
    return signature


def preservation_signature_leq3(relation: Relation) -> int:
    return _signature(relation.arity, relation.mask)


def common_signature(relations: Iterable[Relation]) -> int:
    signature = ALL_OPERATION_MASK
    for relation in relations:
        signature &= preservation_signature_leq3(relation)
    return signature


def signature_operations(signature: int) -> tuple[tuple[int, int], ...]:
    return tuple(operation for index, operation in enumerate(OPERATIONS) if (signature >> index) & 1)


def signature_names(signature: int) -> tuple[str, ...]:
    return tuple(name for name, bit in NAMED_WITNESSES.items() if signature & bit)


def gained_operations(before: int, after: int) -> tuple[tuple[int, int], ...]:
    return signature_operations(after & ~before)


def gained_witnesses(before: int, after: int) -> tuple[str, ...]:
    return tuple(
        name for name, bit in NAMED_WITNESSES.items()
        if not before & bit and after & bit
    )


def signature_hex(signature: int) -> str:
    return f"0x{signature:069x}"

