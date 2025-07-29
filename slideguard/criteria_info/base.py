from pydantic import BaseModel
from dataclasses import dataclass
from typing import Literal

@dataclass
class CriterionInfo:
    criterion_name: str
    criterion_type: Literal["slide", "deck"]
    criterion_description: str
    criterion_prompt: str
    criterion_schema: BaseModel