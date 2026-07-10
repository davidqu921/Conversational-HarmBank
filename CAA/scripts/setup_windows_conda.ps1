$ErrorActionPreference = "Stop"

$Conda = "C:\Users\david\miniconda3\Scripts\conda.exe"
$Python = "C:\Users\david\miniconda3\envs\caa\python.exe"
$EnvPath = "C:\Users\david\miniconda3\envs\caa"

if (-not (Test-Path $EnvPath)) {
    Write-Host "Creating caa environment..."
    & $Conda create -n caa python=3.11 pip -y
} else {
    Write-Host "Conda environment already exists: $EnvPath"
}

Write-Host "Installing CUDA PyTorch..."
& $Python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

Write-Host "Installing CAA Transformers dependencies..."
& $Python -m pip install -r CAA\requirements-transformers.txt

Write-Host "Verifying CUDA..."
& $Python -c "import torch; print('torch', torch.__version__); print('cuda available', torch.cuda.is_available()); print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
