$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$py = Join-Path $Root ".venv-train\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Run setup-environment.ps1 first" }
New-Item -ItemType Directory -Force -Path "data" | Out-Null

& $py -c @"
import os, scipy.io.wavfile
from datasets import load_dataset
from tqdm import tqdm

out = 'data/mit_rirs'
os.makedirs(out, exist_ok=True)
if len(os.listdir(out)) < 10:
    ds = load_dataset('davidscripka/MIT_environmental_impulse_responses', split='train', streaming=True)
    for row in tqdm(ds, desc='mit_rirs'):
        name = row['audio']['path'].split('/')[-1]
        scipy.io.wavfile.write(os.path.join(out, name), 16000, (row['audio']['array'] * 32767).astype('int16'))
print('mit_rirs ok')
"@

$files = @{
  "data/openwakeword_features_ACAV100M_2000_hrs_16bit.npy" = "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/openwakeword_features_ACAV100M_2000_hrs_16bit.npy"
  "data/validation_set_features.npy" = "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main/validation_set_features.npy"
}
foreach ($rel in $files.Keys) {
  if (-not (Test-Path $rel)) {
    Write-Host "Downloading $rel (large, may take a while)..."
    Invoke-WebRequest -Uri $files[$rel] -OutFile $rel
  }
}

& $py -c @"
import os, scipy.io.wavfile
from datasets import load_dataset
from tqdm import tqdm
out = 'data/fma'
os.makedirs(out, exist_ok=True)
if len([f for f in os.listdir(out) if f.endswith('.wav')]) < 10:
    import datasets as ds
    fma = iter(load_dataset('rudraml/fma', name='small', split='train', streaming=True).cast_column('audio', ds.Audio(sampling_rate=16000)))
    for i in tqdm(range(120), desc='fma'):
        row = next(fma)
        name = row['audio']['path'].split('/')[-1].replace('.mp3', '.wav')
        scipy.io.wavfile.write(os.path.join(out, name), 16000, (row['audio']['array'] * 32767).astype('int16'))
print('fma ok')
"@

# Use fma-only backgrounds if audioset not present
if (-not (Test-Path "data/audioset_16k")) {
  Write-Host "Note: audioset skipped (large). config uses data/fma for backgrounds."
}

Write-Host "Data download step complete."
