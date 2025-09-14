from pydantic import BaseModel, Field

class PredictRequest(BaseModel):
    """Payload used to predict sentiment of a text."""
    text: str = Field(min_length=1, max_length=512, description="Text to predict sentiment of")

class PredictResponse(BaseModel):
    """Response from the model."""
    label: str = Field(description="Sentiment of the text")
    score: float = Field(description="Score of the sentiment")
    modelId: str = Field(min_length=1, description="Identifier of the model")
