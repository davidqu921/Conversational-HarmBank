$ErrorActionPreference = "Continue"

Write-Host "== GPU =="
nvidia-smi

Write-Host "`n== Windows Python =="
where.exe python
python --version
where.exe pip
pip --version

Write-Host "`n== Hugging Face Env =="
Get-ChildItem Env:HF_TOKEN,Env:HUGGINGFACE_HUB_TOKEN,Env:HF_HOME,Env:TRANSFORMERS_CACHE -ErrorAction SilentlyContinue |
    Select-Object Name, Value

Write-Host "`n== WSL =="
wsl -l -v

