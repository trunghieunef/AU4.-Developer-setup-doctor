# Developer Setup Doctor

CLI chẩn đoán môi trường thiết lập cho một repository: SDK, dependencies, dịch vụ cục bộ,
kèm bước khắc phục chính xác và kết quả machine-readable (JSON + exit code).

## Tính năng

- 🧩 **6 nhóm checker**: Node.js, Python, Java, .NET, dịch vụ cục bộ (Docker/DB/Redis), registry/credentials
- 🔍 **2 chế độ chẩn đoán**:
  - `flat` — checklist phẳng từng mục
  - `dep` — gom lỗi theo **nguyên nhân gốc** (root cause) qua đồ thị phụ thuộc, chỉ rõ sửa gì trước
- 📦 **Output**: terminal (human-readable) + JSON (machine-readable) + exit code
- 🛠️ **`--fix` có kiểm soát**: chỉ áp dụng remediation `safe_fix` trong whitelist, có backup + log; chỉ thao tác reversible mới rollback được — không tự thay đổi khi thiếu `--fix`
- 🤖 **AI tăng cường (tùy chọn)**: gợi ý lệnh sửa động + giải thích nguyên nhân tự nhiên, có fallback rule-based
- 🔬 **`study`**: harness nghiên cứu so sánh flat vs dep (deterministic, không dùng AI)

## Cài đặt

```bash
pip install -e ".[dev]"        # phát triển
pip install -e ".[ai]"         # thêm hỗ trợ AI (openai/anthropic)
```

## Sử dụng

```bash
setup-doctor check <repo>                  # chẩn đoán (mặc định mode=dep, text)
setup-doctor check <repo> --mode flat      # checklist phẳng
setup-doctor check <repo> --format json    # JSON machine-readable
setup-doctor check <repo> --format json --output report.json  # ghi JSON ra file
setup-doctor check <repo> --fix            # áp dụng remediation trong whitelist (có backup)
setup-doctor check <repo> --ai             # tăng cường AI (cần SETUP_DOCTOR_API_KEY)
setup-doctor study repos.txt --ground-truth research/ground_truth --output-dir research/output
setup-doctor --version
```

Exit codes: `0` = pass hoặc không thuộc ecosystem hỗ trợ, `1` = có lỗi (severity error), `2` = lỗi nội bộ.

## Cấu hình

Tạo file `setup-doctor.toml` (xem chi tiết spec mục 4.8):

```toml
[mode]
default = "dep"            # flat | dep

[ai]
enabled = false            # bật AI (CLI --ai ghi đè)
provider = "openai"        # openai | anthropic
model = "gpt-4o-mini"
max_requests = 10
timeout_sec = 20

[output]
format = "text"            # text | json
```

Ưu tiên: `CLI flag > env (SETUP_DOCTOR_*) > config file > default`.

## An toàn

- Mặc định **read-only**: chạy check không thay đổi gì trong repo.
- `--fix` chỉ áp dụng các remediation có `safe_fix=true`, `source=manual` và operation nằm trong whitelist; backup vào `.setup-doctor-backup/<timestamp>/`. Chỉ operation reversible mới được rollback; install/restore/start-service có thể không đảo ngược và luôn được ghi rõ trong log.
- AI chỉ gửi `check_id`/evidence đã lọc/OS lên LLM; **không gửi credentials hay nội dung file repo**; API key đọc từ env `SETUP_DOCTOR_API_KEY`.
- Nghiên cứu (`study`) luôn chạy **rule-based** — deterministic, tái lập được.

## Nghiên cứu

`setup-doctor study` so sánh hai chế độ (flat vs dep) theo precision/recall/accuracy/clarity/f1
trên các repo thực tế với ground truth ghi chú thủ công.

Tài liệu chi tiết:

- Spec: `docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md`
- Kế hoạch triển khai: `docs/superpowers/plans/2026-09-15-developer-setup-doctor.md`
