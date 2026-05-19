"""GPU adapter package: protocols, device detection, local implementations."""

from pd_ocr_ops.gpu.default_stages import register_default_stages
from pd_ocr_ops.gpu.device import pick_device
from pd_ocr_ops.gpu.local_stage import LocalStageDispatcher
from pd_ocr_ops.gpu.protocols import LongJobRunner, StageDispatcher
from pd_ocr_ops.gpu.types import (
    BatchJobItem,
    BatchJobResult,
    BatchProgressCb,
    DispatchModel,
    GPUBackend,
    OcrPageRequest,
    OcrPageResponse,
    ProcessPageRequest,
    ProcessPageResponse,
)

__all__ = [
    "BatchJobItem",
    "BatchJobResult",
    "BatchProgressCb",
    "DispatchModel",
    "GPUBackend",
    "LocalStageDispatcher",
    "LongJobRunner",
    "OcrPageRequest",
    "OcrPageResponse",
    "ProcessPageRequest",
    "ProcessPageResponse",
    "StageDispatcher",
    "pick_device",
    "register_default_stages",
]
