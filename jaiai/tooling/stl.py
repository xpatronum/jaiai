import copy
import itertools

import torch
from loguru import logger


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


def _other_props(d: dict, include_keys: list[str] | None = None, flatten_meta_props: bool = False) -> dict:
    """
    Filter a source document to a selected subset of keys and optionally
    hoist properties from a nested "meta" mapping to the top level.

    Args:
        d: Source document as a dictionary.
        include_keys: List of keys to keep from the source. If None, keep all keys.
        flatten_meta_props: If True and the result contains a "meta" dict,
            remove "meta" and merge its key/value pairs into the top level
            (one level only; inner dicts under "meta" are preserved as-is).
            Useful to normalize docs for document store, where metadata is expected
            at the top level.

    Returns:
        A new dictionary containing only the requested keys and, if enabled,
        the hoisted metadata properties.

    Example:
        Input:
            {
            "content": "Document content",
            "meta": {
                "useful_links": {
                "images": ["link1", "link2"],
                "wiki": ["wiki_link1", "wiki_link2"]
                }
            }
            }

        With include_keys=None and flatten_meta_props=True:
            {
            "content": "Document content",
            "useful_links": {
                "images": ["link1", "link2"],
                "wiki": ["wiki_link1", "wiki_link2"]
            }
            }
    """
    must_include_keys = d.keys() if include_keys is None else include_keys
    js_answer = {key: d[key] for key in must_include_keys if key in d}
    if flatten_meta_props and "meta" in js_answer:
        js_meta_props = _other_props(js_answer.pop("meta"))
    else:
        js_meta_props = {}
    return {**js_answer, **js_meta_props}


def merge_iterators(*iterators):
    return itertools.chain(*iterators)


def merge_in_order(a: dict | None = None, dv: dict | None = None, do_copy: bool = False):
    """
    This function perfrorm `merge` in a Asymmetric way.
    Standard `a.update(dv)` doesn't change with argument swapping.
    Hence we need to wrap them around.

    Args:
        a (Optional[Dict], optional): _description_. Defaults to None.
        dv (Optional[Dict], optional): _description_. Defaults to None.
        do_copy (bool, optional): _description_. Defaults to False.

    Returns:
        _type_: Dict
        _description_: Positional merge of two different dict(s) as described.
    """
    # {**{ key: value }, **default_values} On average it is faster!
    a = a or dict()
    dv = dv or dict()
    if do_copy:  # noqa: SIM108
        response = copy.deepcopy(a)
    else:
        response = a
    response = {**dv, **response}
    return response


def initialize_device_settings(use_gpus, local_rank=-1, use_amp=None, **props):
    if not use_gpus:
        device = torch.device("cpu")
        n_gpu = 0
    elif local_rank == -1:
        if torch.cuda.is_available():
            device, n_gpu = torch.device("cuda"), torch.cuda.device_count()
        elif torch.backends.mps.is_available():
            device, n_gpu = torch.device("mps"), 1
        else:
            device, n_gpu = "cpu", 0
    else:
        if torch.backends.mps.is_available():
            device, n_gpu = "mps", 1
        elif not torch.cuda.is_available():
            msg = f"You specified [local_rank={local_rank}] but CUDA is not available."
            logger.error(msg)
            raise ValueError(msg)
        else:
            device = torch.device("cuda", local_rank)
            torch.cuda.set_device(device)
            n_gpu = 1
            # Initializes the distributed backend which will take care of sychronizing nodes/GPUs
            torch.distributed.init_process_group(backend="nccl")
    logger.info(f"Using device: {str(device).upper()} ")
    logger.info(f"Number of GPUs: {n_gpu}")
    logger.info(f"Distributed Training: {bool(local_rank != -1)}")
    logger.info(f"Automatic Mixed Precision: {use_amp}")
    return device, n_gpu
