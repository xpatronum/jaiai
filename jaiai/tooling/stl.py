import itertools


class alist(list):
    async def __aiter__(self):
        for _ in self:
            yield _


class AsyncConstructor(object):  # noqa
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance


class NIterator:
    __slots__ = ("_is_next", "_the_next", "it")

    def __init__(self, it):
        self.it = iter(it)
        self._is_next = None
        self._the_next = None

    def has_next(self) -> bool:
        if self._is_next is None:
            try:
                self._the_next = next(self.it)
            except:  # noqa: E722
                self._is_next = False
            else:
                self._is_next = True
        return self._is_next

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        if self._is_next:  # noqa: SIM108
            response = self._the_next
        else:
            response = next(self.it)
        self._is_next = None
        return response


def chunkify(f, chunksize=10_000_000, sep="\n"):
    """
    Read a file separating its content lazily.

    Usage:

    >>> with open('INPUT.TXT') as f:
    >>>     for item in chunkify(f):
    >>>         process(item)
    """
    chunk = None
    remainder = None  # data from the previous chunk.
    while chunk != "":
        chunk = f.read(chunksize)
        if remainder:  # noqa: SIM108
            piece = remainder + chunk
        else:
            piece = chunk
        pos = None
        while pos is None or pos >= 0:
            pos = piece.find(sep)
            if pos >= 0:
                if pos > 0:
                    yield piece[:pos]
                piece = piece[pos + 1 :]
                remainder = None
            else:
                remainder = piece
    if remainder:  # This statement will be executed iff @remainder != ''
        yield remainder


def merge_iterators(*iterators):
    return itertools.chain(*iterators)
