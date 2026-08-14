from __future__ import annotations

from collections.abc import Iterable, Sequence


class ByteTokenizer:
    """Lossless UTF-8 byte tokenizer with a fixed, reproducible vocabulary."""

    vocab_size = 256

    def encode(self, text: str) -> list[int]:
        return list(text.encode("utf-8"))

    def decode(self, token_ids: Iterable[int]) -> str:
        values = list(token_ids)
        if any(isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 255 for item in values):
            raise ValueError("token ids must be integers from 0 through 255")
        return bytes(values).decode("utf-8", errors="strict")


class NextTokenDataset(Sequence[tuple[tuple[int, ...], tuple[int, ...]]]):
    """In-memory next-token windows for fixtures and bounded reference runs."""

    def __init__(
        self,
        texts: Iterable[str],
        tokenizer: ByteTokenizer,
        sequence_length: int,
        *,
        stride: int | None = None,
        maximum_samples: int = 10000,
    ) -> None:
        if sequence_length < 1:
            raise ValueError("sequence_length must be positive")
        resolved_stride = stride or sequence_length
        if resolved_stride < 1:
            raise ValueError("stride must be positive")
        if maximum_samples < 1:
            raise ValueError("maximum_samples must be positive")
        samples: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
        for text in texts:
            ids = tokenizer.encode(text)
            for start in range(0, max(0, len(ids) - sequence_length), resolved_stride):
                window = ids[start : start + sequence_length + 1]
                if len(window) != sequence_length + 1:
                    continue
                samples.append((tuple(window[:-1]), tuple(window[1:])))
                if len(samples) > maximum_samples:
                    raise ValueError("dataset exceeds maximum_samples")
        self._samples = tuple(samples)

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, index: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
        return self._samples[index]
