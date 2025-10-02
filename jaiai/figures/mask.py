import abc

import polars as pl


class IChart(abc.ABC):
    @abc.abstractmethod
    def view(self, data: pl.DataFrame, **props):
        pass

    @abc.abstractmethod
    def save(self, filename, ppi=200):
        pass
        # self.chart.save(filename, ppi=ppi)
