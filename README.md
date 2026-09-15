# Developer Setup Doctor

> Bác sĩ thiết lập môi trường cho nhà phát triển — chẩn đoán một repository về SDK, dependencies và dịch vụ cục bộ, đưa ra bước khắc phục chính xác và kết quả machine-readable (JSON + exit code).

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20first-lightgrey)](docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Tính năng

- 🧩 **6 nhóm checker**: Node.js, Python, Java, .NET, dịch vụ cục bộ (Docker/PostgreSQL/Redis), registry/credentials
- 🔍 **2 chế độ chẩn đoán** trên cùng một bộ check:
  - `flat` — checklist phẳng từng mục
  - `dep` (**mặc định**) — gom lỗi theo **nguyên nhân gốc** (root cause) qua đồ thị phụ thuộc, chỉ rõ sửa gì trước
- 📦 **Output đa dạng**: terminal (human-readable) + JSON (machine-readable, schema 1.0) + exit code chuẩn
- 🛠️ **`--fix` có kiểm soát**: chỉ áp dụng remediation nằm trong **operation whitelist** (argv an toàn, không shell operator), có backup + log; **re-check sau khi sửa** để trả exit code của trạng thái cuối
- 🤖 **AI tăng cường (tùy chọn)**: gợi ý lệnh sửa động + giải thích nguyên nhân tự nhiên — có `sanitize`, quota chung, validate schema, **fallback rule-based** khi AI không khả dụng
- 🔬 **`study` harness**: so sánh định lượng flat vs dep (deterministic, không dùng AI) phục vụ nghiên cứu

## Yêu cầu hệ thống

- **Python ≥ 3.11**
- **Windows-first**: MVP chạy chính trên Windows (remediation theo OS mặc định Windows). Hỗ trợ Linux/macOS là roadmap — chưa tuyên bố đa nền tảng đầy đủ.

## Cài đặt

```bash
# Phát triển (kèm pytest)
pip install -e ".[dev]"

# Hoặc bản thường
pip install -e .

# Thêm hỗ trợ AI (openai/anthropic)
pip install -e ".[ai]"
```

## Sử dụng nhanh

```bash
# Chẩn đoán repo (mặc định: mode=dep, output text)
setup-doctor check /path/to/repo

# Checklist phẳng thay vì root-cause
setup-doctor check /path/to/repo --mode flat

# Output JSON machine-readable (dùng cho CI/script)
setup-doctor check /path/to/repo --format json --output report.json

# Áp dụng remediation an toàn (có backup, có re-check)
setup-doctor check /path/to/repo --fix

# Tăng cường AI (cần API key — xem phần Cấu hình)
setup-doctor check /path/to/repo --ai

# Nghiên cứu: so sánh flat vs dep trên nhiều repo
setup-doctor study repos.txt --ground-truth research/ground_truth --output-dir research/output

# Phiên bản
setup-doctor --version
```

### Ví dụ output thực tế (repo `expressjs/express` sau khi clone)

```
setup-doctor report (mode: dep)
repo: C:\tmp\sd-repo-express | os: windows
summary: {'total': 10, 'pass': 4, 'fail': 2, 'skip': 4, 'warnings': 0}
[PASS] node.runtime.present:  node v24.14.1 at C:\Program Files\nodejs\node.EXE
[PASS] node.sdk.version:      node v24.14.1 expected >= 18
[PASS] node.pkgmgr.present:   npm at C:\Program Files\nodejs\npm.CMD
[FAIL] node.lockfile.exists:  no lockfile found
    fix 1: Generate lockfile -> npm install --package-lock-only
[FAIL] node.deps.installed:   node_modules missing
    fix 1: Install dependencies from lockfile -> npm ci
[SKIP] node.build.ready: no build script declared
[PASS] registry.git.user: user.name/email set
[SKIP] registry.git.ssh: remote uses HTTPS; no SSH key needed
[SKIP] registry.npm: npm not found or no registry line in .npmrc
[SKIP] registry.pypi: no pip.conf/pip.ini in repo
root causes:
  - node.lockfile.exists: Lockfile exists is a root cause of 2 failing check(s)
    (chain: node.lockfile.exists -> node.deps.installed)
exit_code: 1
```

> **Cách đọc:** tool chỉ **đọc** (không tự sửa). `--fix` mới thay đổi — và chỉ với operation trong whitelist.

### Exit codes

| Code | Ý nghĩa |
|---|---|
| `0` | Tất cả check pass, **hoặc** repo không thuộc ecosystem hỗ trợ (output đúng format đã chọn) |
| `1` | Có ≥ 1 check `fail` (severity `error`) |
| `2` | Path repo không tồn tại / không phải thư mục, **hoặc** lỗi nội bộ tool |

## Check đang hỗ trợ (catalog)

| Ecosystem | Checks |
|---|---|
| **Node.js** | `node.runtime.present`, `node.package_json.valid`, `node.sdk.version`, `node.pkgmgr.present`, `node.lockfile.exists`, `node.deps.installed`, `node.build.ready` |
| **Python** | `python.runtime.present`, `python.version`, `python.env.present` (yêu cầu `pyvenv.cfg`), `python.deps.installed`, `python.build.ready` |
| **Java** | `java.runtime.present`, `java.version`, `java.maven.gradle.present`, `java.deps.cached` (warning), `java.build.ready` |
| **.NET** | `dotnet.runtime.present`, `dotnet.sdk.version`, `dotnet.restore.ready` (warning), `dotnet.build.ready` |
| **Services** | `services.container.present`, `services.compose.up`, `services.db.port`, `services.redis`, `services.envfile` |
| **Registry** | `registry.git.user` (warning), `registry.git.ssh` (warning, skip khi remote HTTPS), `registry.npm`, `registry.pypi` |

Phát hiện ecosystem tự động qua marker file (`package.json`, `pyproject.toml`, `pom.xml`, `*.sln`, `docker-compose.yml`...). Xem chi tiết: **spec mục 3.7**.

## Cấu hình

Tự động tìm `setup-doctor.toml` theo thứ tự: `--config <path>` → thư mục repo → thư mục hiện tại → `~/.setup-doctor/setup-doctor.toml`.

```toml
[mode]
default = "dep"            # flat | dep

[ai]
enabled = false            # bật AI (CLI --ai/--no-ai ghi đè)
provider = "openai"        # openai | anthropic
model = "gpt-4o-mini"
max_requests = 10          # quota chung cho tất cả AI requests
timeout_sec = 20

[output]
format = "text"            # text | json
```

**Thứ tự ưu tiên:** `CLI flag > env (SETUP_DOCTOR_*) > config file > default`.

### Environment variables

| Biến | Ý nghĩa |
|---|---|
| `SETUP_DOCTOR_MODE` | Chế độ mặc định (`flat`/`dep`) |
| `SETUP_DOCTOR_FORMAT` | Format mặc định (`text`/`json`) |
| `SETUP_DOCTOR_AI` | Bật AI (`1`/`true`/`yes`) |
| `SETUP_DOCTOR_AI_MODEL` | Model AI |
| `SETUP_DOCTOR_API_KEY` | API key cho AI (chỉ đọc từ env, không lưu trong file) |

## An toàn

- **Mặc định read-only**: chạy `check` không thay đổi gì trong repo (chỉ đọc file, stat, chạy `--version`, TCP probe).
- **`--fix` giới hạn**:
  - Chỉ áp dụng remediation có `safe_fix=true`, `source=manual` và **operation trong whitelist**.
  - Backup vào `.setup-doctor-backup/<timestamp>/` trước khi sửa.
  - **Rollback** chỉ đảm bảo cho operation **reversible** (file cấu hình nhỏ đã backup, vd `create-env`). Install/restore/start-service là **non-reversible** và luôn được ghi rõ trong log.
  - Chống path traversal: file trong `step.files` phải nằm trong repo.
  - **Re-check sau fix** — exit code phản ánh trạng thái cuối cùng (không phải trước fix).
- **AI**: chỉ gửi `check_id`/evidence đã `sanitize`/OS lên LLM; không gửi credentials/nội dung file repo; API key chỉ từ env; quota chung; LLM không bao giờ quyết định `status`/`severity`.
- **Nghiên cứu (`study`)**: luôn chạy rule-based — deterministic, tái lập được.

## Phát triển

```bash
# Cài editable + dev deps
pip install -e ".[dev]"

# Chạy toàn bộ test (81 tests)
python -m pytest

# Chạy theo nhóm
python -m pytest tests/unit/          # unit
python -m pytest tests/integration/   # integration (fixer, cli)
python -m pytest tests/unit/test_engine.py -k dep   # riêng DAG dep mode
```

### Cấu trúc thư mục

```
src/setup_doctor/
├── cli.py            # CLI (check/study, exit codes, tri-state --ai)
├── config.py         # TOML config + env + CLI (độ ưu tiên)
├── models.py         # CheckResult, Report, Diagnosis, RemediationStep
├── registry.py       # Phát hiện ecosystem + plugin checker (entry points)
├── runner.py         # Pipeline: validate → detect → checkers → engine → AI
├── engine.py         # Flat mode + dep mode (DAG, root causes)
├── output.py         # Text / JSON renderer
├── fixer.py          # --fix: whitelist op, backup, reversible-only rollback
├── checkers/         # 6 checker read-only (plugin-style)
├── ai/               # Provider + remediation + explainer (opt-in)
├── study/            # Metrics + ground truth + CSV/JSON runner
└── utils/            # run_command, versions, osdetect
```

### Kiến trúc

- **Checkers read-only**: mỗi ecosystem là một `Checker`, trả `list[CheckResult]`; KHÔNG chạy lệnh có side-effect khi check.
- **Engine tách khỏi checkers**: chỉ làm việc trên `CheckResult` — dễ test bằng fixture.
- **Fixer tách khỏi engine**: engine chỉ chẩn đoán, fixer chỉ sửa.
- **Plugin-style**: thêm checker mới = thêm module + 1 dòng entry point trong `pyproject.toml` (kèm fallback import trực tiếp khi metadata rỗng).

## Nghiên cứu (AU4 - Research & Evaluate)

`setup-doctor study` so sánh hai chế độ theo **precision / recall / accuracy / clarity / f1** trên universe `expected_failures ∪ expected_passes` của ground truth. Các metric precision/recall/accuracy/f1 **giống hệt nhau** giữa flat và dep (vì cùng bộ check) — sự khác biệt nằm ở **clarity** (độ chính xác root cause) và đánh giá người dùng (thủ công). Chi tiết: **spec mục 4.7, 5**.

## Tài liệu

- **Spec**: `docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md` (v1.3)
- **Kế hoạch triển khai**: `docs/superpowers/plans/2026-09-15-developer-setup-doctor.md`

## License

MIT
