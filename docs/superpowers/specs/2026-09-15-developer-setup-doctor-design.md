# Developer Setup Doctor — Thiết kế

- **Ngày:** 2026-09-15
- **Status:** Đã duyệt (Ready for implementation planning)
- **Người duyệt:** Người dùng (đã xác nhận trong phiên brainstorming)

---

## 1. Brief (Tóm tắt)

### 1.1 Bối cảnh

Các nhà phát triển (đặc biệt là người mới) thường mất rất nhiều thời gian để thiết lập môi trường chạy dự án cục bộ: SDK thiếu version, dependencies chưa cài, dịch vụ cục bộ chưa khởi động, credentials chưa cấu hình. Các hướng dẫn hiện có thường là checklist tĩnh (README), không chỉ ra **nguyên nhân gốc** và **thứ tự sửa** hợp lý.

### 1.2 Vấn đề

- Người dùng mới không biết lỗi nào là **nguyên nhân gốc (root cause)**, lỗi nào là **hệ quả**.
- Checklist phẳng liệt kê mọi thiếu sót nhưng không giải thích **tại sao** và **sửa gì trước**.
- Không có output **machine-readable** để CI hoặc script tự động hóa việc kiểm tra.

### 1.3 Mục tiêu (Goal)

Xây một CLI tool **Developer Setup Doctor** đa nền tảng, kiểm tra **một repository** về SDK, dependencies và các điều kiện tiên quyết về dịch vụ cục bộ, sau đó xuất ra **các bước khắc phục chính xác** kèm **kết quả machine-readable** (JSON + exit code).

### 1.4 Câu hỏi nghiên cứu (Research question)

> Liệu **diagnosis nhận biết quan hệ phụ thuộc** (dependency-aware diagnosis) có giải thích lỗi thiết lập **tốt hơn checklist phẳng** (flat checklist) không?

### 1.5 Tiêu chí đánh giá (Evaluation criteria)

1. **Độ chính xác chẩn đoán** đối với các vấn đề thiết lập đã được **cấy sẵn có chủ đích** (seeded problems — dùng trong unit test).
2. **Thời gian đến khi build cục bộ thành công** (time to a successful local build) — đo thủ công theo hướng dẫn của tool trên repo thực tế.
3. **Tính lặp lại** (repeatability): các kiểm tra lặp lại được **không âm thầm thay đổi cấu hình developer** (mọi thay đổi chỉ qua `--fix` có backup + log).

### 1.6 Phạm vi

**Trong phạm vi (MVP):**

- Kiểm tra **một repository** tại một thời điểm.
- Hỗ trợ 6 nhóm checker: Node.js, Python, Java, .NET, dịch vụ cục bộ, registry/credentials.
- 2 chế độ chẩn đoán: `flat` và `dep` (dependency-aware), chạy **cùng bộ check**.
- Output: terminal (human-readable) + JSON (machine-readable) + exit code.
- Tùy chọn `--fix` an toàn (có backup) — chỉ in các bước nếu không dùng `--fix`.
- Research harness (`setup-doctor study`) để so sánh 2 chế độ trên repo thực tế.
- Ưu tiên Windows; kiến trúc đủ linh hoạt để mở rộng Linux/macOS sau.

**Ngoài phạm vi (YAGNI):**

- Không làm HTML report.
- Không tự sửa credentials.
- Không hỗ trợ chạy nhiều repo trong một lần gọi (chỉ 1 repo; study harness lặp nhiều repo riêng).
- Không watch mode / daemon.
- Không hỗ trợ các ecosystem khác ngoài 6 nhóm trên ở MVP.

---

## 2. PRD (Product Requirements Document)

### 2.1 Người dùng & kịch bản

| Người dùng | Kịch bản chính |
|---|---|
| **Developer mới** (người dùng chính) | Clone repo → chạy `setup-doctor check <repo>` → nhận danh sách lỗi + bước sửa → làm theo → build thành công nhanh |
| **Developer có kinh nghiệm** | Chạy `--fix` để tự động cài deps / tạo `.env` an toàn; dùng JSON để tích hợp CI |
| **Nhà nghiên cứu / đánh giá** | Chạy `setup-doctor study` trên 10-20 repo thực tế → xuất bảng so sánh flat vs dep |

### 2.2 Yêu cầu chức năng (Functional requirements)

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-1 | CLI nhận path repo, tự phát hiện ecosystem (package.json, pyproject.toml, pom.xml, *.sln, docker-compose.yml...) | P0 |
| FR-2 | Kiểm tra SDK version theo yêu cầu của repo (`.nvmrc`, `engines`, `.python-version`, `global.json`, `.sdkmanrc`...) và đối chiếu version đang cài | P0 |
| FR-3 | Kiểm tra dependencies: package manager có mặt, lockfile tồn tại, `node_modules`/venv/cache khớp | P0 |
| FR-4 | Kiểm tra dịch vụ cục bộ: Docker daemon, Postgres/MySQL/Redis/Mongo (qua port hoặc `docker ps`) | P0 |
| FR-5 | Kiểm tra registry/credentials: npm registry, pip index, git user/SSH, credentials tồn tại (không đọc nội dung) | P1 |
| FR-6 | Hai chế độ chẩn đoán `--mode=flat` (checklist) và `--mode=dep` (DAG + gom root cause) | P0 |
| FR-7 | Output JSON chuẩn hóa ra stdout/file + exit code (0 pass, 1 có lỗi, 2 lỗi nội bộ) | P0 |
| FR-8 | Remediation: mỗi check fail kèm các bước sửa chính xác (lệnh cụ thể) | P0 |
| FR-9 | `--fix`: tự áp dụng các remediation an toàn có backup + log đầy đủ | P1 |
| FR-10 | `setup-doctor study`: chạy nhiều repo, đối chiếu ground truth, tính metrics | P0 |
| FR-11 | Không bao giờ tự sửa cấu hình developer khi không có `--fix` | P0 |

### 2.3 Yêu cầu phi chức năng (Non-functional requirements)

| ID | Yêu cầu | Chi tiết |
|---|---|---|
| NFR-1 | **An toàn**: mọi thao tác sửa chỉ qua `--fix` + backup; không xóa file người dùng; không sửa credentials | Mặc định read-only |
| NFR-2 | **Repeatable**: cùng repo + cùng môi trường → cùng kết quả; không thay đổi trạng thái khi chạy check | Đầu ra ổn định |
| NFR-3 | **Hiệu năng**: mỗi lệnh có timeout 30s; tổng thời gian chạy < 2 phút cho 1 repo | - |
| NFR-4 | **Khả năng mở rộng**: thêm checker mới = thêm 1 module, không sửa framework | Plugin-style |
| NFR-5 | **Đa nền tảng (ưu tiên Windows)**: lệnh remediation có phiên bản theo OS, tự phát hiện OS | - |
| NFR-6 | **Độ chính xác**: checker phát hiện đúng >= 90% lỗi seeded trong fixture | Kiểm chứng bằng test |
| NFR-7 | **JSON schema ổn định**: version hóa schema (`schema_version`) | - |

### 2.4 Tiêu chí chấp nhận (Acceptance criteria)

- **AC-1**: Với repo Node mẫu thiếu SDK + `node_modules`, `--mode=flat` liệt kê ≥ 1 lỗi; `--mode=dep` xác định root cause `node.sdk.version` và đánh dấu `deps.install`, `build.run` là `caused_by`.
- **AC-2**: Output JSON khớp schema 1.0; `summary`, `checks`, `diagnosis` đúng cấu trúc.
- **AC-3**: `--fix` tạo backup trước khi sửa; sau khi fix, repo build được; log ghi rõ mọi thay đổi.
- **AC-4**: `setup-doctor study` nhận ground truth JSON, xuất CSV/JSON với precision, recall, accuracy, clarity đúng.
- **AC-5**: Chạy check 2 lần trên cùng repo không làm thay đổi gì trên repo (mtime git status sạch nếu không có `--fix`).
- **AC-6**: Với repo không phải ecosystem hỗ trợ, exit code 0 + message "no supported ecosystem detected".

---

## 3. Architecture (Kiến trúc)

### 3.1 Tổng quan

```
┌─────────────────────────────────────────────────────────────┐
│                     setup-doctor (CLI)                        │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │  CLI      │──▶│  Checker      │──▶│  Diagnosis Engine    │  │
│  │  argparse │   │  Registry     │   │  ┌───────────────┐   │  │
│  │          │   │  (load & run) │   │  │ Flat Mode     │   │  │
│  └──────────┘   └──────┬───────┘   │  ├───────────────┤   │  │
│                        │           │  │ Dependency-    │   │  │
│                        ▼           │  │ aware Mode     │   │  │
│  ┌──────────────────────────────┐  │  └───────┬───────┘   │  │
│  │  Checkers (each ecosystem)   │  │          ▼            │  │
│  │  Node │ Python │ Java │ .NET │  │  ┌──────────────┐     │  │
│  │  Services │ Registry          │  │  │ Output        │     │  │
│  └──────────────────────────────┘  │  │ (Terminal +   │     │  │
│                                    │  │  JSON + Exit)  │     │  │
│  ┌──────────────────────────────┐  │  └──────────────┘     │  │
│  │ Research Harness (--study)    │──▶ Mỗi repo → JSON       │  │
│  │   (ground truth, metrics)     │    → so sánh 2 mode      │  │
│  └──────────────────────────────┘  │                       │  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Các khối

| Khối | Trách nhiệm | Phụ thuộc |
|---|---|---|
| **CLI** (`cli.py`, dùng `argparse`) | Parse args: repo path, `--mode`, `--format`, `--fix`, `--study`; đọc config tool; gọi orchestration | Registry |
| **Checker Registry** (`registry.py`) | Đăng ký các checker class, tự phát hiện ecosystem từ cấu trúc repo, chọn checker phù hợp, chạy theo thứ tự | Checkers |
| **Checkers** (`checkers/*.py`, 6 module) | Mỗi module trả về `list[CheckResult]`; **read-only**; không tự sửa config | CheckContext |
| **Diagnosis Engine** (`engine.py`) | Chạy 2 chế độ trên cùng bộ `CheckResult`; dep mode dựng DAG, gom root cause, sắp xếp ảnh hưởng | CheckResult |
| **Output** (`output.py`) | Format text cho terminal, JSON cho máy, exit code; schema version | Report |
| **Fixer** (`fixer.py`) | `--fix`: backup vào `.setup-doctor-backup/<ts>/`, áp dụng remediation `safe_fix`, log mọi thay đổi | Report |
| **Research Harness** (`study.py`) | Đọc list repo + ground truth, chạy cả 2 mode mỗi repo, tính metrics, xuất CSV/JSON | Engine, Output |
| **Context** (`context.py`) | `CheckContext`: repo path, OS, config tool, kết quả check đã chạy (để checker khác đọc) | — |

### 3.3 Luồng dữ liệu (Data flow)

1. CLI nhận lệnh → Registry phát hiện ecosystem → chọn checker.
2. Mỗi checker chạy, ghi kết quả vào `CheckContext` → trả `list[CheckResult]`.
3. Engine nhận `list[CheckResult]` → nếu `flat`: sắp xếp theo nhóm; nếu `dep`: dựng DAG, gom root cause.
4. Output định dạng → text ra terminal, JSON ra file/stdout, exit code.
5. Nếu `--fix`: Fixer đọc report, backup, áp dụng remediation an toàn, cập nhật log.
6. Nếu `--study`: Harness lặp bước 1-4 trên nhiều repo, đối chiếu ground truth, xuất bảng metrics.

### 3.4 Kiến trúc hướng đơn vị nhỏ, tách bạch

- Mỗi checker là một đơn vị độc lập: rõ mục đích, interface (`run(ctx) -> list[CheckResult]`), phụ thuộc duy nhất là `CheckContext`.
- Engine tách khỏi checkers: engine chỉ làm việc trên `CheckResult` (không đọc file, không chạy lệnh) → dễ test bằng fixture `CheckResult`.
- Fixer tách khỏi engine: engine chỉ chẩn đoán, fixer chỉ sửa — không trộn trách nhiệm.
- Cải thiện codebase hiện tại: workspace hiện chỉ có `README.md` trống, nên không có refactor cần thiết.

### 3.5 Xử lý lỗi

| Tình huống | Xử lý |
|---|---|
| Lệnh không tồn tại | Checker báo `skip` kèm lý do; không coi là lỗi nếu ecosystem không liên quan |
| Repo không phải ecosystem hỗ trợ | "no supported ecosystem detected" + exit 0 |
| Command timeout (30s) | `fail` + remediation "tăng timeout / kiểm tra môi trường" |
| Parse lỗi trong config project | `fail` + evidence lỗi parse cụ thể |
| Lỗi nội bộ tool | Exit 2 + stack trace; không thay đổi repo |
| `--fix` lỗi giữa chừng | Khôi phục từ backup, báo lỗi rõ ràng |

### 3.6 Testing

| Loại | Nội dung |
|---|---|
| **Unit test checker** | Fixture seeded repos (3-5 mỗi checker: pass, fail thiếu SDK, fail sai version...) → đảm bảo phát hiện đúng |
| **Unit test engine** | Fixture `CheckResult` → DAG, root cause, sorting đúng |
| **Snapshot test JSON** | Schema 1.0 ổn định, không breaking change |
| **Integration `--fix`** | Fixture repo → backup được tạo, sửa đúng, không đụng file ngoài phạm vi |
| **Test research harness** | Fixture ground truth → metrics tính đúng |

---

## 4. Interfaces (Giao diện)

### 4.1 CLI

```
setup-doctor check <repo_path> [--mode flat|dep] [--format text|json] [--output <file>] [--fix] [--verbose]
setup-doctor study <repos_file> [--ground-truth <json>] [--output-dir <dir>]
setup-doctor --version
```

| Option | Mô tả | Mặc định |
|---|---|---|
| `check <repo_path>` | Kiểm tra một repo | bắt buộc |
| `--mode flat\|dep` | Chế độ chẩn đoán | `dep` |
| `--format text\|json` | Định dạng output | `text` |
| `--output <file>` | Ghi JSON ra file (chỉ dùng với `--format json`) | stdout |
| `--fix` | Áp dụng remediation an toàn (có backup) | tắt |
| `--verbose` | Log chi tiết | tắt |
| `study <repos_file>` | Chạy nghiên cứu nhiều repo | — |

### 4.2 Data model — `CheckResult`

```json
{
  "check_id": "node.sdk.version",
  "name": "Node.js SDK version",
  "ecosystem": "node",
  "severity": "error",
  "status": "fail",
  "evidence": "Node v18.16.0 found (expected >=20.0.0)",
  "remediation": [
    { "step": "Install Node 22 LTS via nvm", "command": "nvm install 22", "safe_fix": true },
    { "step": "Switch to it", "command": "nvm use 22", "safe_fix": true }
  ],
  "depends_on": ["node.runtime.present"],
  "caused_by": null
}
```

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `check_id` | string | Định danh duy nhất của check |
| `name` | string | Tên hiển thị |
| `ecosystem` | string | `node` \| `python` \| `java` \| `dotnet` \| `services` \| `registry` |
| `severity` | enum | `error` \| `warning` \| `info` |
| `status` | enum | `pass` \| `fail` \| `skip` |
| `evidence` | string | Bằng chứng (version tìm thấy, output lệnh...) |
| `remediation` | array | Các bước sửa, mỗi bước có `command` + `safe_fix` |
| `depends_on` | array[string] | Các check_id tiên quyết (dùng bởi dep mode) |
| `caused_by` | string \| null | Chỉ dep mode: check_id root cause gây ra check này |

### 4.3 Data model — `Report`

```json
{
  "schema_version": "1.0",
  "repo_path": "/path/to/repo",
  "os": "windows",
  "mode": "dep",
  "generated_at": "2026-09-15T10:00:00Z",
  "summary": { "total": 24, "pass": 18, "fail": 4, "skip": 2, "warnings": 3 },
  "checks": [],
  "diagnosis": {
    "root_causes": [
      {
        "cause_check_id": "node.sdk.version",
        "message": "Node SDK is outdated",
        "affected_checks": ["node.sdk.version", "deps.install", "build.run"],
        "chain": "node.sdk → deps.install → build.run"
      }
    ]
  },
  "exit_code": 1
}
```

| Trường | Ý nghĩa |
|---|---|
| `schema_version` | Version schema (1.0) |
| `repo_path`, `os`, `mode` | Metadata |
| `generated_at` | Timestamp ISO 8601 |
| `summary` | Thống kê total/pass/fail/skip/warnings |
| `checks` | Mảng `CheckResult` |
| `diagnosis` | Chỉ trong dep mode: `root_causes` (gom nguyên nhân gốc + chuỗi ảnh hưởng) |
| `exit_code` | 0 = pass, 1 = có lỗi, 2 = lỗi nội bộ |

### 4.4 Exit codes

| Code | Ý nghĩa |
|---|---|
| `0` | Tất cả check pass, hoặc repo không thuộc ecosystem hỗ trợ |
| `1` | Có ít nhất 1 check `fail` (severity error) |
| `2` | Lỗi nội bộ tool (exception, không liên quan repo) |

### 4.5 Interfaces giữa các khối

```
Checker.run(ctx: CheckContext) -> list[CheckResult]
Engine.diagnose(checks: list[CheckResult], mode: str) -> Report
Output.render(report: Report, format: str) -> str
Fixer.apply(report: Report, backup_dir: Path) -> FixReport
Study.run(repos: list[Path], ground_truth: dict) -> StudyReport
```

### 4.6 Ground truth format (cho `study`)

```json
{
  "repo": "https://github.com/example/repo",
  "local_path": "/repos/example",
  "expected_failures": ["node.sdk.version"],
  "expected_root_causes": ["node.sdk.version"],
  "notes": "Thiếu SDK version; node_modules chưa cài"
}
```

### 4.7 Metrics nghiên cứu

| Metric | Định nghĩa |
|---|---|
| **precision** | Số lỗi tool dự đoán đúng ÷ tổng số lỗi tool báo |
| **recall** | Số lỗi tool dự đoán đúng ÷ tổng số lỗi thực tế (ground truth) |
| **accuracy** | (TP + TN) ÷ tổng checks |
| **clarity** | Dep mode: tỷ lệ root cause chính xác theo ground truth |
| **f1** | Harmonic mean của precision & recall |
| **time_to_build** | Đo thủ công: từ lúc chạy tool → build thành công (sample) |

---

## 5. Kế hoạch triển khai (giai đoạn)

| Giai đoạn | Nội dung |
|---|---|
| **1. Skeleton** | CLI + data model + JSON schema + output formatter + exit code |
| **2. 2 checker đầu** (Node + Python) | Kèm seeded fixture repos + unit test → chứng minh framework |
| **3. 4 checker còn lại** | Java, .NET, Services, Registry |
| **4. Diagnosis Engine** | Flat mode → dep mode (DAG + root cause) |
| **5. `--fix` an toàn** | Backup + apply + log |
| **6. Research Harness** | Ground truth format, metrics, CSV/JSON báo cáo |
| **7. Nghiên cứu** | Clone 10-20 repo, labeling, chạy study, tổng hợp |
| **8. Báo cáo** | Viết kết quả so sánh flat vs dep |

---

## 6. Rủi ro & giả định

| Rủi ro | Giảm thiểu |
|---|---|
| Repo thực tế có cấu trúc đa dạng, khó dự đoán | Tự phát hiện ecosystem linh hoạt; checker bỏ qua mục không liên quan (`skip`) |
| Version SDK/manager thay đổi | Đối chiếu theo file spec của repo (`.nvmrc`, `engines`, `global.json`...), không hardcode bản mới nhất |
| Dịch vụ cục bộ không có Docker | Kiểm tra port trực tiếp + cho phép dùng native service |
| Thời gian label ground truth lớn | 10-20 repo; ưu tiên repo phổ biến, cấu trúc chuẩn |
| Lệnh `--fix` gây hại | Backup trước, `safe_fix` whitelist, log đầy đủ, không sửa credentials |
```