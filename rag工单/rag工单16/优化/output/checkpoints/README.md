---
library_name: peft
license: other
base_model: /home/zzy/LLaMA-Factory/models/Qwen2.5-VL-3B-Instruct
tags:
- base_model:adapter:/home/zzy/LLaMA-Factory/models/Qwen2.5-VL-3B-Instruct
- llama-factory
- lora
- transformers
pipeline_tag: text-generation
model-index:
- name: checkpoints
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# checkpoints

This model is a fine-tuned version of [/home/zzy/LLaMA-Factory/models/Qwen2.5-VL-3B-Instruct](https://huggingface.co//home/zzy/LLaMA-Factory/models/Qwen2.5-VL-3B-Instruct) on the vlm_mini dataset.
It achieves the following results on the evaluation set:
- Loss: 0.1459

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 0.0002
- train_batch_size: 1
- eval_batch_size: 1
- seed: 42
- gradient_accumulation_steps: 4
- total_train_batch_size: 4
- optimizer: Use OptimizerNames.ADAMW_TORCH_FUSED with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: cosine
- lr_scheduler_warmup_ratio: 0.03
- num_epochs: 1
- mixed_precision_training: Native AMP

### Training results



### Framework versions

- PEFT 0.18.1
- Transformers 4.57.6
- Pytorch 2.11.0+cu130
- Datasets 4.0.0
- Tokenizers 0.22.2