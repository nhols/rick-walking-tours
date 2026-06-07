from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, ClassVar, Literal, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelRequest, UserPromptPart
from sqlalchemy import JSON, Column
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, Relationship, SQLModel


type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
type MessageHistory = list[ModelMessage]


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    awaiting_input = "awaiting_input"
    complete = "complete"
    failed = "failed"


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    complete = "complete"
    failed = "failed"


class TourInput(BaseModel):
    location: str = PydanticField(min_length=1)
    description: str = PydanticField(min_length=1)


class TourInputJSON(TypeDecorator[TourInput]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: TourInput | None, dialect: Dialect) -> JSONValue | None:
        if value is None:
            return None
        return cast(JSONValue, value.model_dump(mode="json"))

    def process_result_value(self, value: object | None, dialect: Dialect) -> TourInput | None:
        if value is None:
            return None
        return TourInput.model_validate(value)


class MessageHistoryJSON(TypeDecorator[MessageHistory]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: MessageHistory | None, dialect: Dialect) -> JSONValue:
        if value is None:
            return []
        return cast(JSONValue, ModelMessagesTypeAdapter.dump_python(value, mode="json"))

    def process_result_value(self, value: object | None, dialect: Dialect) -> MessageHistory:
        if value is None:
            return []
        return ModelMessagesTypeAdapter.validate_python(value)


def now_utc() -> datetime:
    return datetime.now(UTC)


class Job(SQLModel, table=True):
    __tablename__: ClassVar[str] = "jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: JobStatus = Field(default=JobStatus.pending, index=True)
    input: TourInput = Field(sa_column=Column(TourInputJSON(), nullable=False))
    current_stage: str = Field(default="checkpoint_research", index=True)
    created_at: datetime = Field(default_factory=now_utc, index=True)

    stages: list["Stage"] = Relationship(back_populates="job")


class Stage(SQLModel, table=True):
    __tablename__: ClassVar[str] = "stages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(foreign_key="jobs.id", index=True)
    name: str = Field(index=True)
    status: StageStatus = Field(default=StageStatus.pending, index=True)
    state: MessageHistory = Field(
        default_factory=list,
        sa_column=Column(MessageHistoryJSON(), nullable=False),
    )

    job: Job = Relationship(back_populates="stages")


class JobCreate(BaseModel):
    input: TourInput


class ApproveEvent(BaseModel):
    type: Literal["approve"]


class FeedbackEvent(BaseModel):
    type: Literal["feedback"]
    message: str = PydanticField(min_length=1)


type JobEvent = Annotated[ApproveEvent | FeedbackEvent, PydanticField(discriminator="type")]


class StageRead(BaseModel):
    id: UUID
    job_id: UUID
    name: str
    status: StageStatus
    state: MessageHistory

    model_config = {"from_attributes": True}


class JobRead(BaseModel):
    id: UUID
    status: JobStatus
    input: TourInput
    current_stage: str
    created_at: datetime
    stages: list[StageRead]

    model_config = {"from_attributes": True}


class JobSummary(BaseModel):
    id: UUID
    status: JobStatus
    input: TourInput
    current_stage: str
    created_at: datetime


def user_message(content: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=content)])


def app_message(content: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=content)])
