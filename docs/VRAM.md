# VRAM Management for shadow-qwen

GTX 1070 (8GB) მომხმარებლებისთვის და ნებისმიერი მცირე-VRAM
სისტემისთვის. Ollama-ს default ქცევა model-ს VRAM-ში ინახავს
**5 წუთი** ბოლო request-ის შემდეგ (keep-alive timeout) რათა
მომდევნო prompt-ი მყისიერი იყოს.

## VRAM სტატუსის შემოწმება

```bash
# GPU-ს load
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader

# რომელი model არის ამჟამად VRAM-ში
curl -s http://localhost:11434/api/ps | python -m json.tool
# ან
ollama ps
```

გამოსავალი მაგალითი:
```
NAME                  ID              SIZE      PROCESSOR    UNTIL
shadow-qwen:latest    c85153778ce9    7.0 GB    100% GPU     4 minutes from now
```

---

## VRAM-ის სრული გათავისუფლება — 3 მეთოდი

### 1. Keep-alive 0 (recommended)

ყველაზე სუფთა, ყველაზე სწრაფი — ollama-ს ეუბნება მაშინვე
გადმოტვირთოს კონკრეტული model:

```bash
curl -s http://localhost:11434/api/generate \
  -d '{"model":"shadow-qwen:latest","keep_alive":0}'
```

ერთ წამში VRAM გათავისუფლდება. სხვა model-ებზე ეფექტი არ აქვს.

### 2. ყველა loaded model-ის გადმოტვირთვა

```bash
for m in $(ollama ps | tail -n +2 | awk '{print $1}'); do
  curl -s http://localhost:11434/api/generate \
    -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null
  echo "unloaded: $m"
done
```

### 3. Ollama service-ის restart (nuclear)

```bash
sudo systemctl restart ollama
```

**ყურადღება:** ეს კლავს ollama-ს ყველა active connection-თან ერთად.
თუ shadow-code სხვა terminal-ში იყო გაშვებული, ის შეცდომას მოგცემს
მომდევნო request-ზე.

---

## Default Keep-alive-ის შეცვლა

თუ ყოველთვის გინდა სწრაფი VRAM გათავისუფლება ყოველი session-ის
შემდეგ, შეცვალე `OLLAMA_KEEP_ALIVE` env var:

```bash
# დროებით (მხოლოდ ამ shell-ში)
export OLLAMA_KEEP_ALIVE=30s

# მუდმივად (~/.zshrc ან ~/.bashrc-ში)
echo 'export OLLAMA_KEEP_ALIVE=30s' >> ~/.zshrc
```

**მნიშვნელოვანი:** ეს env var ollama **service**-ისთვის უნდა დაყენდეს,
არა client-ისთვის. systemd-ით გაშვებული ollama-სთვის:

```bash
sudo systemctl edit ollama
# დაამატე:
[Service]
Environment="OLLAMA_KEEP_ALIVE=30s"

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

ან გადასცე per-request-ად API call-ში: `"keep_alive": "30s"`.

---

## ხშირი მნიშვნელობები

| keep_alive | ქცევა |
|------------|-------|
| `0` ან `0s` | მაშინვე გადმოტვირთვა response-ის შემდეგ |
| `30s` | 30 წამი დახმარიყოს |
| `5m` (default) | 5 წუთი |
| `-1` | მუდამ ჩატვირთული (manual unload-ი საჭირო) |
| `1h` | 1 საათი |

---

## მოსახერხებელი Aliases

დაამატე `~/.zshrc`-ში:

```bash
# VRAM-ის სტატუსი
alias gpu-status='nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv'

# shadow-qwen-ის გადმოტვირთვა
alias gpu-free='curl -s http://localhost:11434/api/generate -d "{\"model\":\"shadow-qwen:latest\",\"keep_alive\":0}" >/dev/null && echo "shadow-qwen unloaded"'

# ყველა model-ის გადმოტვირთვა
gpu-free-all() {
  for m in $(ollama ps | tail -n +2 | awk '{print $1}'); do
    curl -s http://localhost:11434/api/generate \
      -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null
    echo "unloaded: $m"
  done
}
```

გამოყენება:
```bash
gpu-status      # ნახე რამდენი VRAM არის დაკავებული
gpu-free        # მაშინვე გაათავისუფლე shadow-qwen-ი
gpu-free-all    # ყველა loaded model
```

---

## Troubleshooting

**პრობლემა:** `nvidia-smi` აჩვენებს VRAM-ს დაკავებულს, მაგრამ
`ollama ps` ცარიელია.

**მიზეზი:** GPU memory cache (driver ან CUDA-ს მხრიდან). 
Ollama-მ უკვე გადმოტვირთა, მაგრამ driver-მა ჯერ არ გაათავისუფლა.

**გამოსავალი:** რამდენიმე წამის შემდეგ თავისით გასუფთავდება, ან:
```bash
sudo systemctl restart ollama  # nuclear
```

---

**პრობლემა:** shadow-code-მ Ctrl+Z-ით გაჩერდა და process stopped state-ში
დარჩა (`Tl` status `ps`-ში).

**გამოსავალი:**
```bash
ps aux | grep shadow-code | grep -v grep   # იპოვე PID
kill -9 <PID>                              # მოკალი
```

ეს არ ათავისუფლებს VRAM-ს (ollama-ს ეკუთვნის), მაგრამ ნაგავი
process-ი იქნება მოცილებული.
