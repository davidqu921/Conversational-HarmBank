# Windows Conda Setup

This project is currently using a native Windows Conda environment with the
Transformers backend.

## Environment

Conda environment:

```powershell
C:\Users\david\miniconda3\Scripts\conda.exe activate caa
```

Python executable used by scripts:

```powershell
C:\Users\david\miniconda3\envs\caa\python.exe
```

Installed runtime:

- Python 3.11
- PyTorch 2.11.0 + CUDA 12.8
- Transformers 5.13.0
- Hugging Face Hub 1.23.0
- Accelerate 1.14.0

Verified GPU:

- NVIDIA GeForce RTX 5090
- CUDA available from PyTorch

## Hugging Face Login

Do not paste Hugging Face tokens into chat. Log in locally:

```powershell
C:\Users\david\miniconda3\envs\caa\Scripts\hf.exe auth login
```

Use a token that has access to:

- `meta-llama/Llama-3.1-8B-Instruct`
- `google/gemma-2-9b`

After login, verify:

```powershell
C:\Users\david\miniconda3\envs\caa\Scripts\hf.exe auth whoami
```

## Download Models

Default cache path:

```text
D:/Summer_Project_2026/hf_cache
```

Run:

```powershell
C:\Users\david\miniconda3\envs\caa\python.exe CAA\scripts\download_hf_models.py `
  --config CAA\configs\round5_balanced_40.yaml
```

The downloader writes:

```text
D:/Summer_Project_2026/hf_cache/caa_model_manifest.json
```

## Verify Runtime

```powershell
C:\Users\david\miniconda3\envs\caa\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

