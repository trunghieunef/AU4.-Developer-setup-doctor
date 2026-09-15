# Developer Setup Doctor — Thiết kế

- **Ngày:** 2026-09-15
- **Phiên bản:** 1.1
- **Status:** Đã duyệt (Ready for implementation planning)
- **Người duyệt:** Người dùng (đã xác nhận trong phiên brainstorming)
- **Thay đổi v1.1:** bổ sung thiết kế tích hợp AI tùy chọn (AI remediation + AI explainer, tách hoàn toàn khỏi nghiên cứu), catalog check chi tiết, cấu trúc thư mục, cấu hình tool, phương pháp nghiên cứu chi tiết.

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
- **Tích hợp AI tùy chọn (P1, tách khỏi nghiên cứu):**
  - AI gợi ý remediation động theo evidence thực tế (fallback về lệnh viết tay khi AI không khả dụng).
  - AI giải thích chuỗi root cause bằng ngôn ngữ tự nhiên (fallback về mô tả rule-based).
  - Chỉ chạy khi người dùng bật `--ai` + cấu hình API key; **`study` luôn chạy rule-based** để kết quả deterministic và tái lập được.
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

### 2.1a User stories

**Nhóm 1 — Developer mới (người dùng chính)**

| ID | User story | Tiêu chí chấp nhận |
|---|---|---|
| US-1 | Là một developer mới, tôi muốn chạy **một lệnh duy nhất** lên repo vừa clone để biết ngay môi trường còn thiếu gì, để tôi không phải mò mẫm đọc README và thử sai từng lệnh | Chạy `setup-doctor check <repo>` không cần cấu hình trước; output liệt kê rõ mục pass/fail |
| US-2 | Là một developer mới, tôi muốn thấy **các bước sửa chính xác bằng lệnh cụ thể** (không phải mô tả chung chung) cho từng lỗi, để tôi làm theo được ngay dù chưa rành công cụ | Mỗi check fail đều có `remediation[].command` thực thi được theo OS của tôi |
| US-3 | Là một developer mới, tôi muốn biết **lỗi nào là gốc rễ và nên sửa trước**, để tôi không sửa nhầm lỗi hệ quả rồi lại gặp lại lỗi cũ | `--mode=dep` (mặc định) xác định root cause + thứ tự sửa qua `chain` |
| US-4 | Là một developer mới, tôi muốn tool **không tự sửa đổi gì** khi tôi chỉ chạy check, để tôi yên tâm chạy trên máy mà không lo hỏng cấu hình | Chạy check không thay đổi file nào trong repo (AC-5) |

**Nhóm 2 — Developer có kinh nghiệm**

| ID | User story | Tiêu chí chấp nhận |
|---|---|---|
| US-5 | Là một developer có kinh nghiệm, tôi muốn dùng `--fix` để tự động cài dependencies / khởi động service / tạo `.env` an toàn có backup, để tiết kiệm thời gian lặp lại trên nhiều máy | `--fix` tạo backup trước khi đổi; log đầy đủ; rollback nếu lỗi (AC-3) |
| US-6 | Là một developer có kinh nghiệm, tôi muốn lấy **kết quả JSON chuẩn + exit code** để tích hợp vào CI, để pipeline tự chặn build khi môi trường thiếu | `--format json` đúng schema 1.0; exit 1 khi fail, 0 khi pass |
| US-7 | Là một developer có kinh nghiệm, tôi muốn bật `--ai` để nhận **gợi ý sửa lỗi động theo tình huống** và giải thích nguyên nhân tự nhiên, để tiết kiệm thời gian tra cứu khi gặp lỗi lạ | Bật `--ai`: remediation có `source: "ai"`; khi AI lỗi → fallback giữ nguyên, không crash (AC-7) |
| US-8 | Là một developer có kinh nghiệm, tôi muốn cấu hình mặc định (mode, AI, format) qua **file config**, để các lần chạy sau khỏi gõ lại đủ cờ | Config file đọc đúng; CLI flag ghi đè (AC-10) |

**Nhóm 3 — Nhà nghiên cứu / đánh giá**

| ID | User story | Tiêu chí chấp nhận |
|---|---|---|
| US-9 | Là nhà nghiên cứu, tôi muốn chạy `study` trên danh sách repo với **ground truth đã ghi chú**, để so sánh định lượng hai mode flat vs dep | Harness xuất CSV/JSON kèm precision/recall/accuracy/clarity/f1 (AC-4) |
| US-10 | Là nhà nghiên cứu, tôi muốn kết quả nghiên cứu **tái lập được**, để kết quả báo cáo của tôi đáng tin cậy | Chạy `study` 2 lần cùng dữ liệu → kết quả giống hệt (AC-8) |

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
| FR-12 | AI gợi ý remediation động: bật `--ai` → LLM đề xuất lệnh sửa theo evidence + OS; LLM lỗi/offline → fallback về remediation viết tay | P1 |
| FR-13 | AI giải thích root cause: bật `--ai` + `--mode=dep` → LLM viết giải thích tự nhiên cho chuỗi `chain`; fallback về mô tả rule-based | P1 |
| FR-14 | Research cô lập với AI: `study` luôn chạy rule-based; output research không chứa nội dung do LLM sinh | P0 |
| FR-15 | Cấu hình tool qua file config: mode mặc định, AI on/off, provider (openai/anthropic), model, timeout | P1 |

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
| NFR-8 | **AI bảo mật**: không gửi credentials/nội dung nhạy cảm lên LLM; API key chỉ đọc từ env | Whitelist dữ liệu gửi đi |
| NFR-9 | **AI chi phí**: giới hạn số request AI mỗi lần chạy (`max_requests`) | Mặc định 10 |

### 2.4 Tiêu chí chấp nhận (Acceptance criteria)

- **AC-1**: Với repo Node mẫu thiếu SDK + `node_modules`, `--mode=flat` liệt kê ≥ 1 lỗi; `--mode=dep` xác định root cause `node.sdk.version` và đánh dấu `deps.install`, `build.run` là `caused_by`.
- **AC-2**: Output JSON khớp schema 1.0; `summary`, `checks`, `diagnosis` đúng cấu trúc.
- **AC-3**: `--fix` tạo backup trước khi sửa; sau khi fix, repo build được; log ghi rõ mọi thay đổi.
- **AC-4**: `setup-doctor study` nhận ground truth JSON, xuất CSV/JSON với precision, recall, accuracy, clarity đúng.
- **AC-5**: Chạy check 2 lần trên cùng repo không làm thay đổi gì trên repo (mtime git status sạch nếu không có `--fix`).
- **AC-6**: Với repo không phải ecosystem hỗ trợ, exit code 0 + message "no supported ecosystem detected".
- **AC-7**: Bật `--ai` với repo Node thiếu SDK: phần remediation có gợi ý của AI; khi tắt mạng/không có key → kết quả vẫn đầy đủ với lệnh viết tay (không crash, exit code đúng).
- **AC-8**: Chạy `study` 2 lần trên cùng dữ liệu → 2 kết quả giống hệt nhau (deterministic, không có AI trong research).
- **AC-9**: Report JSON không bật `--ai` khớp schema 1.0; khi bật `--ai` chỉ thêm field `ai` (opt-in) không phá vỡ schema cũ.
- **AC-10**: Config file đọc đúng; CLI flag ghi đè config file.

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
| **AI Provider** (`ai/provider.py`) | Interface trừu tượng gọi LLM (OpenAI/Anthropic); quản lý API key (env), model, timeout, retry; trả output đúng schema | Config |
| **AI Remediation** (`ai/remediation.py`) | Dùng `CheckResult` + evidence → LLM gợi ý lệnh sửa; hợp nhất với remediation viết tay (ưu tiên viết tay); fallback khi lỗi | AI Provider, Output |
| **AI Explainer** (`ai/explainer.py`) | Dùng `diagnosis.root_causes` → LLM viết giải thích tự nhiên; fallback về mô tả rule-based | AI Provider, Engine |

### 3.3 Luồng dữ liệu (Data flow)

1. CLI nhận lệnh → Registry phát hiện ecosystem → chọn checker.
2. Mỗi checker chạy, ghi kết quả vào `CheckContext` → trả `list[CheckResult]`.
3. Engine nhận `list[CheckResult]` → nếu `flat`: sắp xếp theo nhóm; nếu `dep`: dựng DAG, gom root cause.
4. *(Tùy chọn)* Nếu `--ai`: AI Remediation gợi ý lệnh sửa cho check fail; AI Explainer viết giải thích root cause — cả hai độc lập, có fallback, không ảnh hưởng logic chẩn đoán.
5. Output định dạng → text ra terminal, JSON ra file/stdout, exit code.
6. Nếu `--fix`: Fixer đọc report, backup, áp dụng remediation an toàn, cập nhật log.
7. Nếu `--study`: Harness lặp bước 1-5 trên nhiều repo (luôn tắt AI), đối chiếu ground truth, xuất bảng metrics.

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
| **Test AI (mock LLM)** | Mock AI Provider trả lời giả lập → remediation/explanation đúng; giả lập lỗi LLM → fallback hoạt động; không gọi API thật trong unit test |

### 3.7 Bảng catalog check chi tiết (6 checkers)

**3.7.1 Node.js (`checkers/node.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `node.runtime.present` | Node có trong PATH | `node` không chạy được | `nvm install 22` (Win: `winget install OpenJS.NodeJS.LTS`) | — |
| `node.sdk.version` | Version đối chiếu `.nvmrc`/`engines` | Version cài < yêu cầu | `nvm use 22` | `node.runtime.present` |
| `node.pkgmgr.present` | npm/yarn/pnpm hiện diện | Thiếu package manager | `corepack enable` | `node.runtime.present` |
| `node.lockfile.exists` | Có lockfile (`package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`) | Thiếu lockfile | `npm install --package-lock-only` | `node.pkgmgr.present` |
| `node.deps.installed` | `node_modules` tồn tại và khớp lockfile | Thiếu/stale | `npm ci` (hoặc `yarn install --frozen-lockfile`) | `node.lockfile.exists`, `node.sdk.version` |
| `node.build.run` | Lệnh build trong `package.json` chạy được | Build script fail | Xem output lỗi; cài lại deps | `node.deps.installed` |

**3.7.2 Python (`checkers/python_ck.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `python.runtime.present` | Python trong PATH | `python`/`py` không chạy | `winget install Python.Python.3.12` | — |
| `python.version` | Version đối chiếu `.python-version`/`pyproject.toml` | Sai version | Cài đúng version qua pyenv/py launcher | `python.runtime.present` |
| `python.env.present` | `.venv`/conda env theo cấu hình | Thiếu venv | `py -m venv .venv` | `python.runtime.present` |
| `python.deps.installed` | Cài đủ theo `requirements.txt`/lock | Thiếu thư viện | `pip install -r requirements.txt` | `python.env.present` |
| `python.build.run` | Test/build entry point chạy được | Fail | Cài lại deps đúng version | `python.deps.installed` |

**3.7.3 Java (`checkers/java.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `java.runtime.present` | JDK trong PATH | Không có `java`/`javac` | `sdk install java` / winget | — |
| `java.version` | JDK version đối chiếu `pom.xml`/`.sdkmanrc` | Sai major version | `sdk install java 21.0.2-tem` | `java.runtime.present` |
| `java.maven.gradle.present` | Maven/Gradle có | Thiếu tool | `winget install Apache.Maven` | `java.runtime.present` |
| `java.deps.resolved` | `.m2`/gradle cache đủ deps (chạy `mvn dependency:resolve` dry) | Thiếu artifact | `mvn dependency:resolve` | `java.maven.gradle.present` |
| `java.build.run` | `mvn compile`/`gradle build` chạy được | Fail | Sửa theo log | `java.deps.resolved` |

**3.7.4 .NET (`checkers/dotnet_ck.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `dotnet.runtime.present` | `dotnet` trong PATH | Không tìm thấy | Winget/installer | — |
| `dotnet.sdk.version` | `global.json`/SDK yêu cầu khớp `dotnet --list-sdks` | Thiếu SDK version | `dotnet-install.ps1` / winget | `dotnet.runtime.present` |
| `dotnet.restore` | `dotnet restore` thành công | NuGet restore fail/offline | `dotnet restore` (kiểm tra nuget.config) | `dotnet.sdk.version` |
| `dotnet.build.run` | `dotnet build` thành công | Compile fail | Sửa theo log | `dotnet.restore` |

**3.7.5 Services (`checkers/services.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `services.container.present` | Docker CLI/daemon (nếu repo dùng compose) | Docker không chạy | Khởi động Docker Desktop | — |
| `services.compose.up` | `docker compose ps` đúng trạng thái | Container chưa chạy | `docker compose up -d` | `services.container.present` |
| `services.db.port` | Port DB (5432/3306/27017...) mở | Port đóng | Khởi động service/native | `services.compose.up` |
| `services.redis` | Redis ping OK (nếu repo dùng) | Không kết nối | `docker compose up redis -d` | `services.compose.up` |
| `services.envfile` | `.env` tồn tại; nếu không → từ `.env.example` | Thiếu `.env` | `cp .env.example .env` (an toàn, có backup) | — |

**3.7.6 Registry/credentials (`checkers/registry.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `registry.git.user` | `git config user.name/email` có | Chưa cấu hình | `git config --global user.name ...` | — |
| `registry.git.ssh` | SSH key tồn tại (không đọc nội dung) | Thiếu key | `ssh-keygen` + thêm vào GitHub | — |
| `registry.npm` | npm registry trỏ đúng (nếu `.npmrc` yêu cầu) | Sai registry | `npm config set registry ...` | `node.runtime.present` |
| `registry.pypi` | pip index trỏ đúng | Sai index | `pip config set global.index-url ...` | `python.runtime.present` |

**Quy ước chung:** check `skip` khi ecosystem không liên quan; remediation phải kèm lệnh cụ thể theo OS; tuyệt đối không tự sửa credentials.

### 3.8 Cấu trúc thư mục dự án

```
setup-doctor/
├── pyproject.toml            # metadata, deps, entry point console script
├── setup-doctor.toml         # config mặc định (đọc từ user hoặc repo)
├── src/setup_doctor/
│   ├── __init__.py
│   ├── cli.py                # argparse: check, study, --version
│   ├── config.py             # config file + env + CLI flag (ưu tiên CLI > env > file)
│   ├── context.py            # CheckContext
│   ├── models.py             # CheckResult, Report, RemediationStep (dataclass + to_dict)
│   ├── registry.py           # CheckerRegistry, auto-detect ecosystem
│   ├── engine.py             # DiagnosisEngine: flat & dep (DAG, root cause)
│   ├── output.py             # TextOutput, JsonOutput, exit code
│   ├── fixer.py              # Fixer: backup + apply + log
│   ├── runner.py             # orchestration tổng (check pipeline)
│   ├── checkers/
│   │   ├── __init__.py       # đăng ký tất cả checker
│   │   ├── base.py           # abstract Checker
│   │   ├── node.py
│   │   ├── python_ck.py
│   │   ├── java.py
│   │   ├── dotnet_ck.py
│   │   ├── services.py
│   │   └── registry.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── provider.py       # AIProvider (openai/anthropic), retry, timeout
│   │   ├── remediation.py    # AIRemediation
│   │   └── explainer.py      # AIExplainer
│   ├── study/
│   │   ├── __init__.py
│   │   ├── ground_truth.py   # load/validate ground truth JSON
│   │   ├── runner.py         # chạy cả 2 mode trên nhiều repo
│   │   └── metrics.py        # precision/recall/accuracy/clarity/f1
│   └── utils/
│       ├── commands.py       # chạy lệnh + timeout 30s + capture output
│       ├── versions.py       # so sánh semver
│       └── osdetect.py       # phát hiện OS, đường dẫn lệnh theo OS
├── tests/
│   ├── fixtures/seeds/       # seeded repos (node_pass/, node_fail_sdk/, ...)
│   ├── unit/test_checkers.py
│   ├── unit/test_engine.py
│   ├── unit/test_ai.py       # mock provider
│   ├── snapshots/            # golden JSON files
│   └── integration/test_fixer.py
└── research/
    ├── repos.txt             # danh sách repo nghiên cứu
    ├── ground_truth/         # JSON ground truth từng repo
    └── output/               # kết quả study (CSV/JSON)
```

### 3.9 Thiết kế AI chi tiết

**Nguyên tắc:** AI là **lớp tăng cường**, không phải thành phần bắt buộc. Mọi logic chẩn đoán vẫn deterministic; AI chỉ bổ sung nội dung hiển thị. Khi AI không khả dụng → output hoàn toàn giống bản không AI.

**3.9.1 AI Remediation (gợi ý lệnh sửa động)**

- **Input:** `CheckResult` (check_id, evidence, remediation viết tay) + OS + version tìm thấy.
- **Prompt:** yêu cầu LLM đưa ra 1-3 lệnh sửa cụ thể phù hợp OS; ưu tiên giữ nguyên lệnh viết tay nếu đúng; trả về JSON theo schema cố định `[{"step": "...", "command": "...", "safe_fix": false}]`.
- **Output:** remediation viết tay **luôn đứng đầu** (đáng tin), gợi ý AI xếp sau, đánh dấu `source: "ai"`.
- **Fallback:** LLM lỗi/timeout/không có key → chỉ dùng remediation viết tay.
- **Giới hạn:** AI không bao giờ quyết định `status`/`severity` — chỉ dùng cho nội dung remediation.

**3.9.2 AI Explainer (giải thích root cause tự nhiên)**

- **Input:** `diagnosis.root_causes` (chuỗi `chain`, message rule-based).
- **Prompt:** giải thích ngắn (≤ 3 câu) theo chuỗi: "Vì X thiếu → Y không chạy → Z fail. Sửa X trước.".
- **Output:** field `ai_explanation` trong `Report.diagnosis` (chỉ khi bật `--ai`).
- **Fallback:** bỏ field, dùng message rule-based.

**3.9.3 Bảo mật & chi phí**

- API key qua env `SETUP_DOCTOR_API_KEY` (không lưu key trong report/config repo).
- Provider `openai`/`anthropic` + model cấu hình; timeout per-request 20s; max 1 retry.
- Giới hạn số request: mỗi lần chạy tối đa `max_requests` (mặc định 10) để tránh chi phí bất ngờ.
- AI chỉ gửi: `check_id`, evidence (đã lọc), OS. Không gửi file repo, credentials, biến môi trường.

---

## 4. Interfaces (Giao diện)

### 4.1 CLI

```
setup-doctor check <repo_path> [--mode flat|dep] [--format text|json] [--output <file>] [--fix] [--ai] [--verbose]
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
| `--ai` | Bật tăng cường AI (remediation động + giải thích root cause); cần API key từ env; bị bỏ qua trong `study` | tắt |
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
    { "step": "Install Node 22 LTS via nvm", "command": "nvm install 22", "safe_fix": true, "source": "manual" },
    { "step": "Switch to it", "command": "nvm use 22", "safe_fix": true, "source": "manual" }
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
| `remediation` | array | Các bước sửa, mỗi bước có `command` + `safe_fix` + `source` (`manual` luôn ưu tiên; `ai` chỉ khi `--ai`) |
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
    ],
    "ai_explanation": null
  },
  "exit_code": 1
}
```

*Ghi chú:* `diagnosis.ai_explanation` là string khi bật `--ai`, `null` khi tắt AI.

| Trường | Ý nghĩa |
|---|---|
| `schema_version` | Version schema (1.0) |
| `repo_path`, `os`, `mode` | Metadata |
| `generated_at` | Timestamp ISO 8601 |
| `summary` | Thống kê total/pass/fail/skip/warnings |
| `checks` | Mảng `CheckResult` |
| `diagnosis` | Chỉ trong dep mode: `root_causes` (gom nguyên nhân gốc + chuỗi ảnh hưởng) |
| `diagnosis.ai_explanation` | *(Chỉ khi bật `--ai`)* Giải thích tự nhiên của LLM cho chuỗi root cause; thiếu → bỏ qua, dùng `message` rule-based |
| `remediation[].source` | `"manual"` (viết tay, luôn ưu tiên) hoặc `"ai"` (gợi ý từ LLM, chỉ khi `--ai`) |
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

### 4.8 Cấu hình tool (config file `setup-doctor.toml`)

```toml
[mode]
default = "dep"            # flat | dep

[ai]
enabled = false            # bật AI (CLI --ai ghi đè)
provider = "openai"        # openai | anthropic
model = "gpt-4o-mini"      # model mặc định theo provider
max_requests = 10          # giới hạn request AI mỗi lần chạy
timeout_sec = 20

[output]
format = "text"            # text | json
```

Ưu tiên: `CLI flag > env (SETUP_DOCTOR_*) > config file > default`.

### 4.9 AI Provider interface (`src/setup_doctor/ai/provider.py`)

```python
class AIProvider(Protocol):
    def complete(self, system: str, user: str, response_schema: type) -> dict | None:
        """Gọi LLM, trả JSON đúng schema; None khi lỗi/timeout → caller tự fallback."""

class OpenAIClient(AIProvider): ...      # dùng thư viện openai
class AnthropicClient(AIProvider): ...   # dùng thư viện anthropic

def get_provider(cfg: ToolConfig) -> AIProvider: ...
```

- Mọi lỗi (network, auth, rate limit, malformed JSON) → bọc trong `AIUnavailableError` → caller fallback.
- Unit test dùng `FakeProvider` (mock), không gọi API thật.

---

## 5. Phương pháp nghiên cứu và đánh giá

### 5.1 Giả thuyết

> **H1:** Diagnosis dependency-aware (dep) giúp developer hiểu **nguyên nhân gốc** và **thứ tự sửa** tốt hơn checklist phẳng (flat), thể hiện qua độ chính xác root cause cao hơn và ít lỗi "hệ quả" bị đếm độc lập hơn.
> **H0:** Không có khác biệt giữa hai mode (nghiên cứu bác bỏ H1 → kết luận dep không vượt trội, vẫn báo cáo trung thực).

### 5.2 Bộ dữ liệu

- **10–20 repo open-source** (GitHub), đa dạng ecosystem: ≥ 3 Node, ≥ 2 Python, 1–2 Java, 1–2 .NET, 2–3 repo có services.
- **Tiêu chí chọn:** mã công khai, có file config chuẩn (3.7), kích thước vừa (build < 10 phút), repo phổ biến (dễ tra cứu tài liệu).
- **Ghim version:** ghi URL + commit hash để lặp lại được (repeatable).

### 5.3 Ground truth (manual labeling)

- Clone repo, chạy build thủ công, ghi chú lỗi thiết lập thực tế theo `check_id` (map với catalog 3.7).
- **2 vòng labeling độc lập**; khác biệt → thảo luận thống nhất (giảm thiên lệch).
- Lưu tại `research/ground_truth/<repo>.json` (schema 4.6).

### 5.4 Quy trình đo time-to-build

- Với 5–8 repo sample: bắt đầu từ trạng thái "repo sạch" (clone mới, chưa cài gì).
- Chạy tool (mode flat hoặc dep theo thứ tự ngẫu nhiên) → đo thời gian chẩn đoán.
- Làm theo remediation → chạy build → ghi thời điểm build thành công.
- Lặp với mode còn lại trên **bản clone riêng** (tránh nhiễu trạng thái).
- Ghi: thời gian chẩn đoán, số bước sửa cần làm, tổng thời gian tới build thành công, số lần build thất bại trước khi thành công.

### 5.5 Metrics & phân tích

- Per-repo: precision/recall/accuracy/clarity/f1 (định nghĩa 4.7).
- **So sánh cặp (paired):** flat vs dep trên cùng repo → báo cáo giá trị trung bình + chênh lệch.
- **Phân tích định tính:** trường hợp dep giúp ích rõ (SDK thiếu → loạt lỗi hệ quả giảm), trường hợp dep không khác (lỗi độc lập).
- **Kết luận:** trả lời câu hỏi nghiên cứu kèm số liệu minh chứng; nêu rõ limitations.

### 5.6 Tính repeatable

- Clone đúng commit hash; chạy tool 2 lần khẳng định cùng output.
- Nếu dùng `--fix` → chạy trên bản clone riêng.
- **Nghiên cứu không dùng AI** (deterministic).

### 5.7 Deliverables

1. Bảng CSV/JSON kết quả per-repo × 2 mode.
2. Tổng hợp metrics + phân tích định tính.
3. Phần "Methodology / Limitations" trong báo cáo cuối.

---

## 6. Kế hoạch triển khai (giai đoạn)

| GĐ | Nội dung | Đầu ra / Tiêu chí hoàn thành |
|---|---|---|
| **1. Skeleton** | `pyproject.toml`, CLI (`check`/`study`/`--version`), models, JSON schema, output text/json, exit code | `setup-doctor --version` chạy được; repo rỗng → exit 0 + "no supported ecosystem detected" |
| **2. Checkers Node + Python** | 2 checker + seeded fixture repos (3-5 bộ/repo) + unit test + snapshot JSON | ≥ 90% seeded phát hiện đúng; pytest pass |
| **3. Checkers còn lại** | Java, .NET, Services, Registry theo catalog 3.7 | Catalog đầy đủ; unit test pass |
| **4. Diagnosis Engine** | Flat mode → dep mode (DAG từ `depends_on`, gom root cause, sort theo ảnh hưởng) | AC-1 pass |
| **5. `--fix` an toàn** | Backup `.setup-doctor-backup/<ts>/`, whitelist `safe_fix`, log mọi thay đổi, rollback khi lỗi | AC-3, AC-5 pass |
| **6. Config + AI Provider** | Config file + độ ưu tiên CLI>env>file; AI provider interface (openai/anthropic) + FakeProvider test | AC-10 pass; unit test AI pass (không gọi API thật) |
| **7. AI Remediator + Explainer** | Gợi ý lệnh sửa động; giải thích root cause; fallback khi AI lỗi; giới hạn request | AC-7, AC-9 pass; fallback đúng |
| **8. Research Harness** | Đọc repos + ground truth, chạy 2 mode, tính metrics, xuất CSV/JSON | AC-4, AC-8 pass |
| **9. Chạy nghiên cứu** | Clone 10-20 repo, 2 vòng labeling, đo time-to-build sample, chạy `study` | Bảng metrics CSV/JSON hoàn chỉnh |
| **10. Báo cáo** | Phân tích số liệu so sánh flat vs dep; trả lời câu hỏi nghiên cứu; phần limitations | Báo cáo nghiên cứu hoàn chỉnh |

**Thứ tự ưu tiên:** GĐ 1-5 = MVP cốt lõi (P0); GĐ 6-7 = AI (P1, sau khi core ổn định); GĐ 8-10 = nghiên cứu & báo cáo.

---

## 7. Rủi ro & giả định

| Rủi ro | Giảm thiểu |
|---|---|
| Repo thực tế có cấu trúc đa dạng, khó dự đoán | Tự phát hiện ecosystem linh hoạt; checker bỏ qua mục không liên quan (`skip`) |
| Version SDK/manager thay đổi | Đối chiếu theo file spec của repo (`.nvmrc`, `engines`, `global.json`...), không hardcode bản mới nhất |
| Dịch vụ cục bộ không có Docker | Kiểm tra port trực tiếp + cho phép dùng native service |
| Thời gian label ground truth lớn | 10-20 repo; ưu tiên repo phổ biến, cấu trúc chuẩn |
| Lệnh `--fix` gây hại | Backup trước, `safe_fix` whitelist, log đầy đủ, không sửa credentials |
| Chi phí/latency khi gọi AI | `max_requests` giới hạn, timeout 20s, fallback rule-based; AI là opt-in |
| Non-determinism của AI | AI tách khỏi nghiên cứu; kết quả AI chỉ là gợi ý hiển thị, không ảnh hưởng chẩn đoán |
| Rò rỉ API key / dữ liệu lên LLM | Key chỉ từ env; chỉ gửi evidence đã lọc (check_id, message, OS); không gửi credentials/file repo |
| LLM trả lời sai lệch (hallucination) | Remediation viết tay luôn ưu tiên đứng đầu; status/severity không bao giờ do AI quyết định |