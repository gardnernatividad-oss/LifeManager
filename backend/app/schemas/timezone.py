from pydantic import BaseModel, ConfigDict


class TimezoneListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]
