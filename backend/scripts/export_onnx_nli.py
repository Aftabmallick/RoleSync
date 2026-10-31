#!/usr/bin/env python3
"""
RoleSync ONNX Quantization & Export Tool
Downloads cross-encoder/nli-deberta-v3-small, exports to ONNX format,
and applies dynamic INT8 quantization for sub-80ms CPU inference.
"""

import argparse
import logging
import os
import pathlib
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export_onnx_nli")


def export_and_quantize_nli(model_name: str, output_dir: pathlib.Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    target_onnx_path = output_dir / "nli_quantized.onnx"
    tokenizer_dir = output_dir / "tokenizer"
    tokenizer_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Preparing to export {model_name} to {target_onnx_path}...")

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError as e:
        logger.error(
            f"Missing dependencies ({e}). Install them via: "
            "pip install transformers torch onnx onnxruntime"
        )
        sys.exit(1)

    logger.info(f"Downloading tokenizer & model weights: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.save_pretrained(tokenizer_dir)

    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()

    raw_onnx_path = output_dir / "nli_raw.onnx"
    dummy_input = tokenizer("Alice developed software", "Alice wrote code", return_tensors="pt")

    logger.info(f"Exporting PyTorch model to raw ONNX: {raw_onnx_path}")
    torch.onnx.export(
        model,
        (dummy_input["input_ids"], dummy_input["attention_mask"]),
        str(raw_onnx_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size"},
        },
        opset_version=14,
    )

    logger.info(f"Applying INT8 dynamic quantization -> {target_onnx_path}")
    quantize_dynamic(
        model_input=str(raw_onnx_path),
        model_output=str(target_onnx_path),
        weight_type=QuantType.QInt8,
    )

    if raw_onnx_path.exists():
        raw_onnx_path.unlink()

    logger.info(f"Quantization complete! Model size: {target_onnx_path.stat().st_size / 1024 / 1024:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Export and quantize NLI cross-encoder to ONNX INT8.")
    parser.add_argument(
        "--model",
        type=str,
        default="cross-encoder/nli-deberta-v3-small",
        help="HuggingFace model identifier",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="backend/models/onnx",
        help="Destination directory for quantized model and tokenizer",
    )
    args = parser.parse_args()

    out_path = pathlib.Path(args.output_dir).resolve()
    export_and_quantize_nli(args.model, out_path)


if __name__ == "__main__":
    main()

