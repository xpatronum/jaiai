import abc
from typing import Generator


class IDataset:
    @abc.abstractmethod
    def iterator(self, **kwargs) -> Generator:
        pass


_all__ = ["IDataset"]
