import os
import re
import logging
from typing import Any, Callable, Optional, Tuple
# NOTE: image helper imports were removed; keep core model utils lean


def _sanitize_model_id(model_id: str) -> str:
    """Sanitize model_id for filesystem safety."""
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", model_id)


def _default_weights_dir() -> str:
    """Return default weights directory path (sibling to this file)."""
    service_dir = os.path.dirname(__file__)
    weights_dir = os.path.join(service_dir, "weights")
    os.makedirs(weights_dir, exist_ok=True)
    return weights_dir


def _weights_path(model_id: str, weights_dir: Optional[str] = None, suffix: str = ".pt") -> str:
    safe_model_id = _sanitize_model_id(model_id)
    base_dir = weights_dir or _default_weights_dir()
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, f"{safe_model_id}{suffix}")


def load_model(
    model_id: str,
    *,
    model_from_pretrained: Callable[[str], Any],
    config_from_pretrained: Optional[Callable[[str], Any]] = None,
    model_from_config: Optional[Callable[[Any], Any]] = None,
    processor_from_pretrained: Optional[Callable[[str], Any]] = None,
    weights_dir: Optional[str] = None,
    save_weights: bool = True,
    logger: Optional[logging.Logger] = None,
    logger_name: Optional[str] = None,
) -> Tuple[Any, Optional[Any]]:
    """
    Load a Transformers model with local weight caching.

    - If a local state_dict exists in weights/{model_id}.pt, instantiate via config and load state.
    - Otherwise, download via model_from_pretrained(model_id) and save state_dict.
    - Optionally also return a processor (tokenizer/processor/image processor) if provided.

    This is generic for text, vision, and multimodal models as long as you pass
    the appropriate constructors for the desired model type.

    Args:
        model_id: The identifier of the model to load.
        model_from_pretrained: A function that loads a model from pretrained.
        config_from_pretrained: A function that loads a config from pretrained.
        model_from_config: A function that loads a model from a config.
        processor_from_pretrained: A function that loads a processor from pretrained.
        weights_dir: The directory to save the weights to.
        save_weights: Whether to save the weights to the weights_dir.

    Returns:
        A tuple containing the model and the processor.
    """
    import torch
    if logger is None:
        logger = logging.getLogger(logger_name) if logger_name else logging.getLogger(__name__)

    weights_path = _weights_path(model_id, weights_dir)

    if os.path.exists(weights_path) and config_from_pretrained and model_from_config:
        config = config_from_pretrained(model_id)
        model = model_from_config(config)
        state_dict = torch.load(weights_path, map_location="cpu")
        model.load_state_dict(state_dict)
        logger.info("Model '%s' loaded from local weights: %s", model_id, weights_path)
    else:
        model = model_from_pretrained(model_id)
        if save_weights:
            try:
                torch.save(model.state_dict(), weights_path)
                logger.info(
                    "Model '%s' downloaded and weights saved to: %s", model_id, weights_path
                )
            except Exception:
                # Best-effort save; continue even if saving fails, include traceback
                logger.warning(
                    "Model '%s' downloaded but failed to save weights to: %s", model_id, weights_path, exc_info=True
                )
        else:
            logger.info("Model '%s' downloaded (weights not saved)", model_id)

    processor = processor_from_pretrained(model_id) if processor_from_pretrained else None
    return model, processor
