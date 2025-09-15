from typing import Optional
from pydantic import BaseModel, Field, model_validator

class PredictRequest(BaseModel):
    """Payload used to predict an answer to a question about an image."""
    # either imageBase64 or imageUrl is required
    imageBase64: Optional[str] = Field(default=None, description="Base64 encoded image")
    imageUrl: Optional[str] = Field(default=None, description="URL of the image")
    question: str = Field(min_length=1, max_length=512, description="Question to answer")

    @model_validator(mode="after")
    def validate_image(self):
        if not self.imageBase64 and not self.imageUrl:
            raise ValueError("Either imageBase64 or imageUrl is required")
        return self

class PredictResponse(BaseModel):
    """Response from the model."""
    answer: str = Field(description="Answer to the question")
    score: float = Field(description="Score of the answer")
    modelId: str = Field(min_length=1, description="Identifier of the model")
