# Developer Setup Doctor

CLI chẩn đoán môi trường phát triển cho repository. Tool tự nhận diện ecosystem, kiểm tra SDK/dependency/service cục bộ, nhóm lỗi theo nguyên nhân gốc, và đưa ra remediation có thể đọc bởi người hoặc máy.

> `check` mặc định là read-only. Chỉ `--fix` mới thực hiện thay đổi, và chỉ với các operation đã được whitelist.

## Điểm nổi bật

- Phát hiện Node.js, Python, Java, .NET, Docker Compose/services và registry configuration từ marker file.
- Hai chế độ chẩn đoán: checklist phẳng (`flat`) hoặc dependency graph/root cause (`dep`, mặc định).
- Terminal UI dùng Rich; JSON thuần cho CI và automation.
- AI tùy chọn: bổ sung gợi ý remediation, có nhãn `[AI]`, quota chung, sanitize evidence và fallback rule-based.
- `--fix` có operation whitelist, backup file liên quan, kiểm tra path traversal và re-check sau khi sửa.
- `study` để so sánh `flat`/`dep` với ground truth và xuất CSV/JSON metrics.

## Hỗ trợ hiện tại

| Ecosystem | Marker | Các kiểm tra chính |
|---|---|---|
| Node.js | `package.json` | runtime, `engines`/`.nvmrc`, npm, lockfile, `node_modules`, build tool |
| Python | `pyproject.toml`, `requirements.txt`, `Pipfile` | runtime, `requires-python`, `.venv`, requirements, build/test declaration |
| Java | `pom.xml`, Gradle files | JDK, version, Maven/Gradle/wrapper, Maven cache, build file |
| .NET | `*.sln`, `*.csproj`, `global.json` | dotnet CLI, SDK, NuGet cache, build files |
| Services | Compose file, `.env.example` | Docker daemon, Compose state, PostgreSQL/Redis TCP port, `.env` |
| Registry | `.npmrc`, pip config, Git remote | Git identity/SSH, npm registry, pip config |

## Yêu cầu

- Python 3.11 trở lên.
- `pipx` được khuyến nghị để dùng CLI từ bất kỳ thư mục nào.
- Remediation rule-based hiện ưu tiên Windows. Checkers chạy trên Linux/macOS, nhưng các command fix nền tảng và coverage package manager chưa đầy đủ.

## Cài đặt

### Dùng CLI từ mọi repository

```bash
# Ubuntu/Debian, nếu chưa có pipx
sudo apt install pipx
pipx ensurepath

# Mở terminal mới, sau đó cài bản local đang phát triển
cd ~/code/Dev-Setup-Doctor
pipx install --editable '.[ai]'

# Kiểm tra
setup-doctor --version
```

`--editable` nghĩa là các thay đổi source được dùng ngay. Khi `pyproject.toml` thay đổi dependency, refresh môi trường pipx:

```bash
pipx reinstall setup-doctor
```

### Phát triển local

```bash
git clone <repository-url>
cd Dev-Setup-Doctor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,ai]'
```

Trên Debian/Ubuntu, nếu không tạo được venv, cài `python3-venv` trước. Không dùng `--break-system-packages` để cài package vào Python hệ thống.

## Bắt đầu nhanh

```bash
# Check repository hiện tại; mode dep là mặc định
setup-doctor check .

# Check repository khác
setup-doctor check ~/code/click

# Checklist phẳng thay vì phân tích root cause
setup-doctor check . --mode flat

# JSON cho CI/script
setup-doctor check . --format json --output report.json

# Chỉ chạy rule-based, không gọi AI
setup-doctor check . --no-ai

# Bật AI nếu đã cấu hình key
setup-doctor check . --ai

# Áp dụng remediation an toàn, backup và check lại
setup-doctor check . --fix

# Xem tất cả options
setup-doctor check --help
```

## Terminal UI và exit code

Output text dùng Rich: header tóm tắt, bảng checks, panel `HOW TO FIX`, `ROOT CAUSES`, và trạng thái AI.

```text
AI: enhanced (openai/gpt-4o-mini); 2 suggestion(s) added
  1. [RULE] Create a virtual environment  $ py -m venv .venv
  2. [AI] Check Python 3 availability  $ python3 --version
```

`[RULE]` là remediation deterministic; `[AI]` là gợi ý bổ sung từ provider. Nếu AI không khả dụng, report vẫn hoàn chỉnh và ghi `AI: unavailable`; tool fallback sang rule-based.

| Exit code | Ý nghĩa |
|---|---|
| `0` | Không có check `error` fail, hoặc không nhận diện ecosystem hỗ trợ |
| `1` | Có ít nhất một check `error` fail |
| `2` | Input path không hợp lệ hoặc lỗi nội bộ |
| `130` | Người dùng hủy bằng Ctrl+C |

`--format json` luôn xuất JSON thuần, không có spinner hoặc terminal UI. `--output` chỉ áp dụng cho JSON.

## AI (tùy chọn)

AI không quyết định `status`, `severity`, root cause hay exit code. Nó chỉ thêm remediation và giải thích root cause sau khi rule-based diagnosis hoàn tất.

### Cấu hình

Tạo cấu hình tool cục bộ, không commit API key:

```bash
mkdir -p ~/.setup-doctor
cp .env.example ~/.setup-doctor/.env
chmod 600 ~/.setup-doctor/.env
```

Sửa `~/.setup-doctor/.env`:

```dotenv
SETUP_DOCTOR_API_KEY="your_api_key"
SETUP_DOCTOR_AI=true
SETUP_DOCTOR_AI_MODEL="gpt-4o-mini"
```

Khi chạy từ repository bất kỳ, tool tìm `.env` theo thứ tự: cạnh file `setup-doctor.toml` được chọn, thư mục hiện tại, rồi `~/.setup-doctor/.env`. Biến môi trường thật luôn ưu tiên hơn `.env`.

Chọn provider/model qua `setup-doctor.toml`:

```toml
[ai]
enabled = true
provider = "openai" # openai | anthropic
model = "gpt-4o-mini"
max_requests = 10
timeout_sec = 20
```

Evidence gửi AI chỉ gồm check ID, OS và evidence đã sanitize; tool không gửi nội dung file repository hay credentials. AI cần API credentials của người dùng hoặc một backend do tổ chức vận hành; không nhúng shared key vào CLI.

## Cấu hình tool

Tool tìm `setup-doctor.toml` theo thứ tự:

1. `--config <path>`
2. `setup-doctor.toml` trong repository được check
3. `setup-doctor.toml` trong thư mục hiện tại
4. `~/.setup-doctor/setup-doctor.toml`

Ví dụ đầy đủ có trong [`setup-doctor.toml.example`](setup-doctor.toml.example). Thứ tự ưu tiên giá trị: CLI flags → environment/`.env` → TOML → defaults.

| Environment variable | Mục đích |
|---|---|
| `SETUP_DOCTOR_MODE` | `flat` hoặc `dep` |
| `SETUP_DOCTOR_FORMAT` | `text` hoặc `json` |
| `SETUP_DOCTOR_AI` | `true`, `yes` hoặc `1` để bật AI |
| `SETUP_DOCTOR_AI_MODEL` | Model AI |
| `SETUP_DOCTOR_API_KEY` | API key của provider |

## Safe fixes

`--fix` chỉ thực thi remediation có `safe_fix=true`, `source=manual` và operation nằm trong whitelist. Các operation gồm cài Node/Python dependencies, tạo venv, restore Java/.NET dependencies, khởi động Docker Compose, tạo `.env` từ `.env.example`, và tạo Node lockfile.

- File khai báo trong remediation phải nằm trong repository (chống path traversal).
- File liên quan được backup vào `.setup-doctor-backup/<timestamp>/`.
- Chỉ thao tác file nhỏ như tạo `.env` có rollback; install/restore/start service là non-reversible.
- Sau fix, tool luôn chạy check lại; exit code phản ánh trạng thái cuối.

Luôn review report trước khi chạy `--fix`, đặc biệt với repository có dependencies hoặc services quan trọng.

## CLI reference

```bash
setup-doctor --version
setup-doctor --help

setup-doctor check <repo_path> [--mode flat|dep] [--format text|json]
                                  [--output report.json] [--fix]
                                  [--ai|--no-ai] [--config path] [--verbose]

setup-doctor study <repos_file> [--ground-truth path] [--output-dir directory]
```

- `--verbose` in traceback khi tool gặp lỗi nội bộ.
- `study` luôn deterministic, không gọi AI.
- `repos_file` chứa một path repository trên mỗi dòng.
- `study` xuất `study_results.csv` và `study_results.json`; output directory mặc định là `research/output`.

## Kiến trúc

```text
CLI → config → ecosystem detection → read-only checkers → diagnosis engine
    → optional AI enrichment → Rich/JSON output
                         └→ optional fixer → re-check
```

```text
src/setup_doctor/
├── cli.py        # command parsing và exit code
├── config.py     # TOML, environment, .env, CLI precedence
├── runner.py     # pipeline check và optional AI
├── engine.py     # flat/dep diagnosis, root causes
├── fixer.py      # whitelist, backup, rollback/re-check flow
├── output.py     # Rich terminal UI và JSON renderer
├── checkers/     # ecosystem-specific read-only checks
├── ai/           # provider, remediation, explainer, quota
├── study/        # ground truth và metrics harness
└── utils/        # commands, versions, OS detection
```

Checker mới được đăng ký qua entry point `setup_doctor.checkers` trong `pyproject.toml`; registry có fallback built-in để test và editable run vẫn hoạt động.

## Phát triển và kiểm thử

```bash
# Cài dependencies dev
python -m pip install -e '.[dev,ai]'

# Toàn bộ suite
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest

# Unit tests hoặc một nhóm cụ thể
.venv/bin/python -m pytest tests/unit/
.venv/bin/python -m pytest tests/unit/test_engine.py -k dep
```

Suite hiện có 92 tests. `python` phải có trong `PATH` khi chạy một số command-runner tests; activate `.venv` hoặc prepend `.venv/bin` như ví dụ trên.

## Giới hạn đã biết

- Python runtime checker hiện tìm `py`/`python`, chưa nhận diện `python3` độc lập trên Linux/macOS. Đây có thể tạo false fail trên một số máy.
- Python dependency check chủ yếu dựa trên `requirements.txt`; project chỉ dùng `pyproject.toml`, `uv.lock`, Poetry hoặc Conda có thể bị `SKIP`.
- Built-in remediation command còn thiên về Windows. AI có thể gợi ý lệnh Linux/macOS nhưng không thay đổi trạng thái check.
- Git identity có severity `warning`, nhưng vẫn có thể xuất hiện trong root-cause panel khi fail.

## Tài liệu và license

- [Design specification](docs/superpowers/specs/2026-09-15-developer-setup-doctor-design.md)
- [Implementation plan](docs/superpowers/plans/2026-09-15-developer-setup-doctor.md)
- License: [MIT](LICENSE)
