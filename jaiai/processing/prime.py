from transformers import PreTrainedTokenizer, PreTrainedTokenizerFast

from jaiai.processing.mask import IProcessor
from jaiai.processing.sample import Sample, SampleBasket
from jaiai.processing.tokenizer import ITokenizer


class INFERProcessor(IProcessor):
    """
    (1) This type of processor is responsible for fast inference using `tokenizers` custom implementation.
    (2) It performs only necessary transformation and avoids typical pre-processing bottleneck such as `regex` use.
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer | PreTrainedTokenizerFast,
        max_seq_len: int = 512,
        do_lower_case: bool = False,
        content_field: str = "content",
        prefix: str = "",
    ):
        super(INFERProcessor, self).__init__()  # noqa: UP008
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len
        self.do_lower_case = do_lower_case
        self.content_field = content_field
        self.prefix = prefix

    @classmethod
    def load(cls, where, config: dict, **kwargs):
        tokenizer = ITokenizer.from_pretrained(where)
        return cls(tokenizer=tokenizer, **config)

    def dataset_from_dicts(self, dicts, indices=None, return_baskets=False):
        if indices is None:
            indices = []
        baskets = []
        docs = [
            self.do_prefix(x=x.get(self.content_field), pref=self.prefix) for x in dicts
        ]

        tokenized_batch = self.tokenizer(
            docs, truncation=True, max_length=self.max_seq_len, padding="max_length"
        )

        input_ids_batch = tokenized_batch["input_ids"]
        atten_ids_batch = tokenized_batch["attention_mask"]

        for sample, input_ids, att_ids in zip(
            docs, input_ids_batch, atten_ids_batch, strict=False
        ):
            tokenized = {}
            features = dict(input_ids=input_ids, attention_mask=att_ids)

            cur_sample = Sample(
                id="", clear_text=sample, tokenized=tokenized, features=[features]
            )
            cur_basket = SampleBasket(
                id_internal=None, raw=sample, id_external=None, samples=[cur_sample]
            )

            baskets.append(cur_basket)

        problematic_ids = set()
        dataset, tensornames = self._create_dataset(baskets)

        if return_baskets:
            return dataset, tensornames, problematic_ids, baskets
        else:
            return dataset, tensornames, problematic_ids
