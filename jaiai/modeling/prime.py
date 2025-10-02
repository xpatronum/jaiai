import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel

from jaiai.modeling.mask import ILanguageModel
from jaiai.processing.mask import IProcessor


class E5GeneralWrapper(ILanguageModel):
    def __init__(self):
        super().__init__()

    def average_pool(self, last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        last_hidden = last_hidden_states.masked_fill(~attention_mask[..., None].bool(), 0.0)

        return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

    def maybe_norm_or_average(self, xs, attention_mask: torch.Tensor, norm: bool, average: bool):
        if average:
            result = self.average_pool(xs, attention_mask=attention_mask)
            if norm:
                result = F.normalize(result, p=2, dim=len(result.shape) - 1)
        elif norm:
            result = F.normalize(xs, p=2, dim=len(xs.shape) - 1)
        else:
            result = xs
        return result


class E5Model(E5GeneralWrapper):
    """Base E5 family semantic model from hugging face"""

    def __init__(
        self,
        model_name_or_instance: str | nn.Module = "intfloat/multilingual-e5-base",
        device="cpu",
        **kwargs,
    ):
        super().__init__()
        self.model = (
            AutoModel.from_pretrained(model_name_or_instance) if isinstance(model_name_or_instance, str) else model_name_or_instance
        )
        self.name = "intfloat/multilingual-e5-base"
        self.model.to(device)

    @classmethod
    def load(cls, model_name_or_path: str, **kwargs):
        model = AutoModel.from_pretrained(model_name_or_path)
        return cls(model, **kwargs)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor = None,
        group_ids: torch.Tensor = None,
        pos_input_ids: torch.Tensor = None,
        pos_attention_mask: torch.Tensor = None,
        norm: bool = True,
        average: bool = True,
    ):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        response = self.maybe_norm_or_average(
            outputs.last_hidden_state,
            attention_mask=attention_mask,
            norm=norm,
            average=average,
        )
        if pos_input_ids is not None and pos_attention_mask is not None:
            pos_outputs = self.model(input_ids=pos_input_ids, attention_mask=pos_attention_mask)
            pos_response = self.maybe_norm_or_average(
                pos_outputs.last_hidden_state,
                attention_mask=pos_attention_mask,
                norm=norm,
                average=average,
            )
            return response, pos_response

        return (response,)


class E5SModel(E5GeneralWrapper):
    """Small E5 family semantic model from huggingface"""

    def __init__(
        self,
        model_name_or_instance: str | nn.Module = "intfloat/multilingual-e5-small",
        device="cpu",
        **kwargs,
    ):
        super().__init__()
        self.model = (
            AutoModel.from_pretrained(model_name_or_instance) if isinstance(model_name_or_instance, str) else model_name_or_instance
        )
        self.name = "intfloat/multilingual-e5-small"
        self.model.to(device)

    @classmethod
    def load(cls, model_name_or_path: str, **kwargs):
        model = AutoModel.from_pretrained(model_name_or_path)
        return cls(model, **kwargs)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor = None,
        group_ids: torch.Tensor = None,
        pos_input_ids: torch.Tensor = None,
        pos_attention_mask: torch.Tensor = None,
        norm: bool = True,
        average: bool = True,
    ):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        response = self.maybe_norm_or_average(
            outputs.last_hidden_state,
            attention_mask=attention_mask,
            norm=norm,
            average=average,
        )
        if pos_input_ids is not None and pos_attention_mask is not None:
            pos_outputs = self.model(
                input_ids=pos_input_ids,
                attention_mask=pos_attention_mask,
                norm=norm,
                average=average,
            )
            pos_response = self.maybe_norm_or_average(
                pos_outputs,
                attention_mask=attention_mask,
                norm=norm,
                average=average,
            )
            return response, pos_response

        return (response,)


class E5LModel(E5GeneralWrapper):
    """Large E5 family semantic model from huggingface"""

    def __init__(
        self,
        model_name_or_instance: str | nn.Module = "intfloat/multilingual-e5-large",
        device="cpu",
        **kwargs,
    ):
        super().__init__()
        self.model = (
            AutoModel.from_pretrained(model_name_or_instance) if isinstance(model_name_or_instance, str) else model_name_or_instance
        )
        self.name = "intfloat/multilingual-e5-large"
        self.model.to(device)

    @classmethod
    def load(cls, model_name_or_path: str, **kwargs):
        model = AutoModel.from_pretrained(model_name_or_path)
        return cls(model, **kwargs)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor = None,
        group_ids: torch.Tensor = None,
        pos_input_ids: torch.Tensor = None,
        pos_attention_mask: torch.Tensor = None,
        norm: bool = True,
        average: bool = True,
    ):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        response = self.maybe_norm_or_average(
            outputs.last_hidden_state,
            attention_mask=attention_mask,
            norm=norm,
            average=average,
        )
        if pos_input_ids is not None and pos_attention_mask is not None:
            pos_outputs = self.model(input_ids=pos_input_ids, attention_mask=pos_attention_mask)
            pos_response = self.maybe_norm_or_average(
                pos_outputs.last_hidden_state,
                attention_mask=pos_attention_mask,
                norm=norm,
                average=average,
            )
            return response, pos_response

        return (response,)


class BGEModel(ILanguageModel):
    def __init__(
        self,
        model_name_or_instance: str | nn.Module = "deepvk/USER-bge-m3",
        device: str = "cpu",
        **kwargs,
    ):
        super().__init__()
        self.model = (
            AutoModel.from_pretrained(model_name_or_instance) if isinstance(model_name_or_instance, str) else model_name_or_instance
        )
        self.name = "deepvk/USER-bge-m3"
        self.model.to(device)

    @classmethod
    def load(cls, model_name_or_path: str, **kwargs):
        model = AutoModel.from_pretrained(model_name_or_path)
        return cls(model, **kwargs)

    def maybe_norm(self, xs, norm: bool):
        if norm:
            return F.normalize(xs, p=2, dim=len(xs.shape) - 1)
        return xs

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor = None,
        group_ids: torch.Tensor = None,
        pos_input_ids: torch.Tensor = None,
        pos_attention_mask: torch.Tensor = None,
        norm: bool = True,
        average: bool = True,
    ):
        # embedding of CLS token
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]

        outputs = self.maybe_norm(outputs, norm=norm)
        if pos_input_ids is not None and pos_attention_mask is not None:
            pos_outputs = self.model(input_ids=pos_input_ids, attention_mask=pos_attention_mask).last_hidden_state[:, 0]

            pos_outputs = self.maybe_norm(pos_outputs, norm=norm)

            return outputs, pos_outputs

        return (outputs,)


HF_CLASS_MAPPING = {
    "intfloat/multilingual-e5-base": E5Model,
    "intfloat/multilingual-e5-small": E5SModel,
    "intfloat/multilingual-e5-large": E5LModel,
    "deepvk/USER-bge-m3": BGEModel,
}
