from typing import List

from pydantic import BaseModel, Field


class Message(BaseModel):
    content: str


# Модель запроса для /is_done
class IsDoneRequest(BaseModel):
    uuid: str


# ---------- I/O models ----------
class ItemIn(BaseModel):
    id: int
    text: str


class PredictIn(BaseModel):
    data: List[ItemIn] = Field(..., min_items=1)


class ItemOut(BaseModel):
    id: int
    topics: List[str]
    sentiments: List[str]


class PredictOut(BaseModel):
    predictions: List[ItemOut]
