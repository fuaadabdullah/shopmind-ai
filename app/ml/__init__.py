"""
Machine Learning module for Torch-based diagnostic classification.

Provides training pipeline, inference, and model registry for v2 intelligence layer.
The ML classifier sits behind the curtain (Layer 1) and injects predictions into
the LLM ranker prompt to bias outcomes toward likely repairs.
"""
