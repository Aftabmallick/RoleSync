# Bundled INT8 Quantized Cross-Encoder NLI Weights

This directory packages the quantized ONNX model weights (`nli_quantized.onnx`) and tokenizer artifacts for production container deployments.

- **Model format**: ONNX IR v9 / Opset 14 INT8 Cross-Encoder
- **Inputs**: `input_ids` (int64 [batch, seq_len]), `attention_mask` (int64 [batch, seq_len])
- **Outputs**: `logits` (float32 [batch, 3]) representing [contradiction, neutral, entailment]
- **Export script**: `backend/scripts/export_onnx_nli.py`
