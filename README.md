# Developer Setup Doctor

> Bác sĩ thiết lập môi trường cho nhà phát triển — chẩn đoán một repository về SDK, dependencies và dịch vụ cục bộ, đưa ra bước khắc phục chính xác và kết quả machine-readable (JSON + exit code).

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20first-lightgrey)](docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Tính năng

### 🧩 Chẩn đoán đa nền tảng codebase (read-only)

Phát hiện ecosystem tự động qua marker file và kiểm tra các điều kiện tiên quyết **mà không sửa gì**:

| Ecosystem | Marker được phát hiện | Kiểm tra chính |
|---|---|---|
| **Node.js** | `package.json` | version theo `engines`/`.nvmrc`, npm, lockfile, `node_modules`, build tool |
| **Python** | `pyproject.toml`, `requirements.txt` | version theo `requires-python`/`.python-version`, venv (`pyvenv.cfg`), deps |
| **Java** | `pom.xml`, `build.gradle` | JDK version, Maven/Gradle/wrapper, cache `.m2`, build file |
| **.NET** | `*.sln`, `*.csproj`, `global.json` | dotnet CLI, SDK version theo `global.json`, NuGet cache, project file |
| **Services** | `docker-compose.yml`, `.env.example` | Docker daemon, compose services, port PostgreSQL/Redis, `.env` |
| **Registry** | `.npmrc`, `pip.conf`, `.git/config` | git user/SSH (warning), npm/pip registry |

Mỗi check có **bằng chứng cụ thể** (version tìm thấy, file tồn tại, lệnh chạy được) và **bước khắc phục chính xác** đi kèm — không đoán mò.

### 🔍 2 chế độ chẩn đoán trên cùng một bộ check

| Chế độ | Cách hoạt động | Khi nào dùng |
|---|---|---|
| `flat` | Checklist phẳng: liệt kê từng check pass/fail độc lập | Muốn thấy toàn cảnh từng mục |
| `dep` (**mặc định**) | Dựng đồ thị phụ thuộc từ `depends_on`, gom lỗi **hệ quả** về **root cause**, vẽ chuỗi `a -> b -> c` và chỉ rõ sửa cái nào trước | Developer mới / muốn biết sửa gì trước |

Ví dụ: thiếu SDK khiến deps không cài được → `dep` gom thành **1 root cause** thay vì 2 lỗi độc lập.

### 📦 Output đa dạng cho người và máy

- **Terminal** — human-readable, dấu `[PASS]/[FAIL]/[SKIP]`, kèm bước sửa và root-cause chain
- **JSON** — machine-readable, schema ổn định (`schema_version: 1.0`), dùng được cho CI/script
- **Exit code chuẩn** — `0` pass, `1` có lỗi, `2` lỗi input/nội bộ

### 🛠️ `--fix` tự sửa an toàn (có kiểm soát)

- Chỉ áp dụng remediation nằm trong **operation whitelist** — lệnh dạng **argv an toàn**, không shell operator
- **Backup** tất cả file bị ảnh hưởng vào `.setup-doctor-backup/<timestamp>/` trước khi sửa
- **Rollback** chỉ đảm bảo cho thao tác **reversible** (file cấu hình nhỏ); install/restore/start-service được đánh dấu **non-reversible** và ghi rõ trong log
- **Re-check sau khi sửa** — exit code phản ánh trạng thái cuối, không phải trước fix
- Chống **path traversal** — file trong `step.files` phải nằm trong repo

### 🤖 AI tăng cường (tùy chọn)

- Gợi ý lệnh sửa **động theo evidence** thực tế + giải thích nguyên nhân tự nhiên
- An toàn: `sanitize` evidence trước khi gửi, **quota chung** giới hạn chi phí, validate schema output
- **Fallback rule-based** hoàn toàn khi AI không khả dụng/key thiếu — không bao giờ crash
- AI không quyết định `status`/`severity` — chỉ bổ sung nội dung hiển thị

### 🔬 `study` — harness nghiên cứu

- Chạy đồng loạt trên nhiều repo, đối chiếu ground truth → metrics **precision/recall/accuracy/clarity/f1**
- **Deterministic** (không dùng AI) → tái lập được kết quả cho nghiên cứu
- Xuất CSV/JSON phục vụ phân tích so sánh `flat` vs `dep`

### 🎯 Nền tảng

- Tự động phát hiện ecosystem qua marker file
- Plugin-style: thêm checker mới = thêm module + entry point, không sửa framework
- Config linh hoạt: file TOML + env + CLI flag

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
