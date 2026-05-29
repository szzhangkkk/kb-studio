"""Pydantic models for tool CRUD operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolParameterProperty(BaseModel):
    type: str = "string"
    description: str = ""
    enum: list[str] | None = None
    default: Any = None


class ToolParameter(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolCreateRequest(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$", min_length=2, max_length=64,
                      description="Tool name in snake_case")
    description: str = Field(..., min_length=4, max_length=500)
    parameters: dict = Field(default_factory=lambda: {"type": "object", "properties": {}})
    code: str = Field(..., min_length=10, max_length=50000,
                      description="Python code with a run(args, context) function")
    tags: list[str] = Field(default_factory=list)


class ToolUpdateRequest(BaseModel):
    description: str | None = Field(None, min_length=4, max_length=500)
    parameters: dict | None = None
    code: str | None = Field(None, min_length=10, max_length=50000)
    enabled: bool | None = None
    tags: list[str] | None = None


class ToolGenerateRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=2000,
                             description="用自然语言描述你想要的工具功能")
    context: str = Field("", max_length=1000,
                         description="额外上下文，比如特定的知识库名、业务逻辑等")


class ToolRefineRequest(BaseModel):
    code: str
    feedback: str = Field(..., min_length=4, max_length=2000)


class ToolTestRequest(BaseModel):
    args: dict = Field(default_factory=dict)
