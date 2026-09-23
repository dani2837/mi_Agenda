from dataclasses import dataclass
from typing import Optional


@dataclass
class Task:
    id: int
    title: str
    description: Optional[str]
    priority: str
    due_date: Optional[str]
    due_time: Optional[str]
    status: str
    created_at: str
    completed_at: Optional[str]


@dataclass
class ShoppingItem:
    id: int
    title: str
    status: str
    created_at: str
    completed_at: Optional[str]
