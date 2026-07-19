from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class Article(BaseModel):
    article_id: str
    source_name: str
    headline: str = Field(..., min_length=1)
    summary: Optional[str] = None
    url: str
    published_at: datetime
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('headline')
    @classmethod
    def clean_headline(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Headline cannot be empty')
        return v
