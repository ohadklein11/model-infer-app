from typing import Optional, List
from pydantic import BaseModel, Field, model_validator

class Box2D(BaseModel):
    """2D bounding box."""
    xmin: float = Field(description="X coordinate of the top-left corner")
    xmax: float = Field(description="X coordinate of the bottom-right corner")
    ymin: float = Field(description="Y coordinate of the top-left corner")
    ymax: float = Field(description="Y coordinate of the bottom-right corner")


class Box(BaseModel):
    """Bounding box."""
    label: str = Field(description="Label of the object")
    box: Box2D = Field(description="Bounding box")


class PredictRequest(BaseModel):
    """Payload used to predict object detection."""
    imageBase64: Optional[str] = Field(default=None, description="Base64 encoded image")
    imageUrl: Optional[str] = Field(default=None, description="URL of the image")

    @model_validator(mode="after")
    def validate_image(self):
        if not self.imageBase64 and not self.imageUrl:
            raise ValueError("Either imageBase64 or imageUrl is required")
        return self


class PredictResponse(BaseModel):
    """Response from the model."""
    boxes: List[Box] = Field(description="List of bounding boxes")
    scores: List[float] = Field(description="List of scores")
    modelId: str = Field(min_length=1, description="Identifier of the model")
    imageBase64: Optional[str] = Field(default=None, description="PNG image with drawn boxes, base64-encoded")
