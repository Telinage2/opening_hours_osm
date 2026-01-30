from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TInterval:
    start: datetime
    end: datetime
    open_end: bool = False
    comment: Optional[str] = None

    def duration(self) -> int:
        """Interval duration in milliseconds"""
        return (self.end - self.start).seconds * 1000

    def __eq__(self, value: object) -> bool:
        if isinstance(value, TInterval):
            return (
                self.start == value.start
                and self.end == value.end
                # and self.open_end == value.open_end
                and self.comment == value.comment
            )
        return False

    def __str__(self) -> str:
        return f"{self.start.isoformat()} - {self.end.isoformat()}"
