# Developer Setup Doctor — Thiết kế

- **Ngày:** 2026-09-15
- **Phiên bản:** 1.3
- **Status:** Đã duyệt (Ready for implementation planning)
- **Người duyệt:** Người dùng (đã xác nhận trong phiên brainstorming)
- **Thay đổi v1.1→v1.2:** sửa theo review round 1.
  - Chuẩn hóa ID check theo catalog (`node.deps.installed`, `node.build.ready`...) và sửa AC-1 cho khớp.
  - Làm rõ ranh giới read-only: **check không chạy lệnh có side-effect** (`mvn dependency:resolve`, `dotnet restore`, `npm ci`, build) — các thao tác này chỉ xảy ra trong `--fix`; check chỉ đọc file/stat/cache/TCP probe.
  - Xóa các check `*.build.run` khỏi catalog để tránh hiểu nhầm chạy build trong check; thay bằng `*.build.ready` (kiểm tra tĩnh).
  - Services, registry: `registry.git.user`/`registry.git.ssh` → **warning**; chỉ chạy registry khi repo có dấu hiệu thật sự cần (git + .npmrc/pip.conf); SSH skip khi remote HTTPS.
  - Tuyên bố rõ **Windows-first** (lệnh remediation theo OS; các lệnh winget/copy/py là của Windows; bản Linux/macOS là roadmap).
  - Metrics nghiên cứu: accuracy tính trên **universe nhãn đã gán** (`expected_failures` ∪ `expected_passes`); `time_to_build` là metric **thủ công ngoài tool** (theo protocol 5.4) — không tính trong harness.
  - AI: redact evidence trước khi gửi; **một quota chung** cho tất cả AI requests (remediation + explainer); validate schema output trước khi hiển thị.
  - Fixer: thiết kế lại theo **transaction**: backup toàn bộ trước, rollback toàn bộ + xóa file mới nếu lỗi, timestamp phút-µs chống trùng, lệnh dạng argv whitelist.
- **Thay đổi v1.2→v1.3 (review round 2):**
  - Version parser: `satisfies` trả `None` cho constraint unsupported → checker báo **warning/skip** (không fail sai); test `~`/`||` sửa đúng.
  - DAG dep-mode: thêm `causes: list[str]` (mọi root causes); `caused_by` giữ primary; xử lý multi-dep fail, skip-bridge, cycle, missing ID.
  - Fixer hạ cam kết rollback: chỉ rollback được file cấu hình nhỏ đã backup (reversible); install/restore/start-service ghi rõ **non-reversible**; chặn path traversal; bỏ xóa mọi path mới tạo.
  - Data model: tách `operation` + `argv` + `command`(display) — whitelist theo operation.
  - Checker semantics: runtime `--version` fail → FAIL; npm/docker thiếu → FAIL; `.venv` yêu cầu `pyvenv.cfg`; deps fail khi thiếu venv; compose so theo prefix name.
  - Cache check (`.m2`/`.nuget`): tồn tại → **warning** (không chứng minh deps repo sẵn sàng); thiếu → FAIL.
  - Metrics: ID trong GT luôn thuộc universe, tool không emit → FN; `validate_ground_truth` reject ID ngoài catalog; nêu rõ flat/dep không khác nhau ở precision/recall.
  - Nhỏ: NFR-3 tách timeout check (30s) vs fix op (timeout riêng); AC-9 chốt schema `ai_explanation` duy nhất (null/string).

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
2. **Thời gian đến khi build cục bộ thành công** (time to a successful local build) — metric **thủ công** đo theo protocol 5.4 (người nghiên cứu làm theo hướng dẫn của tool, bấm giờ) — **không** phải metric tính trong harness.
3. **Tính lặp lại** (repeatability): các kiểm tra lặp lại được **không âm thầm thay đổi cấu hình developer** (check mặc định read-only; mọi thay đổi chỉ qua `--fix` có backup + log).

### 1.6 Phạm vi

**Trong phạm vi (MVP):**

- Kiểm tra **một repository** tại một thời điểm.
- Hỗ trợ 6 nhóm checker: Node.js, Python, Java, .NET, dịch vụ cục bộ, registry/credentials.
- 2 chế độ chẩn đoán: `flat` và `dep` (dependency-aware), chạy **cùng bộ check**.
- Output: terminal (human-readable) + JSON (machine-readable) + exit code.
- Tùy chọn `--fix` có kiểm soát (có backup) — chỉ in các bước nếu không dùng `--fix`.
- Research harness (`setup-doctor study`) để so sánh 2 chế độ trên repo thực tế.
- **Tích hợp AI tùy chọn (P1, tách khỏi nghiên cứu):**
  - AI gợi ý remediation động theo evidence thực tế (fallback về lệnh viết tay khi AI không khả dụng).
  - AI giải thích chuỗi root cause bằng ngôn ngữ tự nhiên (fallback về mô tả rule-based).
  - Chỉ chạy khi người dùng bật `--ai` + cấu hình API key; **`study` luôn chạy rule-based** để kết quả deterministic và tái lập được.
- **Nền tảng: Windows-first** (chạy chính trên Windows; lệnh remediation theo OS, mặc định Windows). Hỗ trợ Linux/macOS là roadmap sau MVP — không tuyên bố đa nền tảng đầy đủ ở MVP.

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
| **Developer có kinh nghiệm** | Chạy `--fix` để tự động cài deps / tạo `.env` theo whitelist; dùng JSON để tích hợp CI |
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
| US-5 | Là một developer có kinh nghiệm, tôi muốn dùng `--fix` để tự động cài dependencies / khởi động service / tạo `.env` theo whitelist, để tiết kiệm thời gian lặp lại trên nhiều máy | `--fix` backup file trước khi đổi; log đầy đủ; rollback các thao tác reversible nếu lỗi (AC-3) |
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
| FR-4 | Kiểm tra dịch vụ cục bộ MVP: Docker daemon, PostgreSQL và Redis (qua port hoặc `docker compose ps`) | P0 |
| FR-5 | Kiểm tra registry/credentials: npm registry, pip index, git user/SSH, credentials tồn tại (không đọc nội dung) | P1 |
| FR-6 | Hai chế độ chẩn đoán `--mode=flat` (checklist) và `--mode=dep` (DAG + gom root cause) | P0 |
| FR-7 | Output JSON chuẩn hóa ra stdout/file + exit code (0 pass, 1 có lỗi, 2 lỗi nội bộ / path không tồn tại) | P0 |
| FR-8 | Remediation: mỗi check fail kèm các bước sửa chính xác (lệnh cụ thể) | P0 |
| FR-9 | `--fix`: tự áp dụng remediation trong whitelist, có backup + log đầy đủ | P1 |
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
| NFR-3 | **Hiệu năng**: mỗi LỆNH CHECK có timeout 30s; tổng thời gian check < 2 phút cho 1 repo. **Lưu ý:** timeout này chỉ áp dụng cho lệnh trong lúc CHECK (đọc). Các op `--fix` (npm ci, mvn resolve, dotnet restore, docker) dùng **timeout riêng dài hơn** trong `_WHITELIST_OP` — không ràng buộc bởi 30s (xem 3.10) | - |
| NFR-4 | **Khả năng mở rộng**: thêm checker mới = thêm 1 module đăng ký vào entry point, không sửa framework | Plugin-style (entry points) |
| NFR-5 | **Windows-first**: MVP hỗ trợ Windows; remediation có OS-specific (mặc định Windows; Linux/macOS roadmap) | - |
| NFR-6 | **Độ chính xác**: checker phát hiện đúng >= 90% lỗi seeded trong fixture | Kiểm chứng bằng test |
| NFR-7 | **JSON schema ổn định**: version hóa schema (`schema_version`) | - |
| NFR-8 | **AI bảo mật**: không gửi credentials/nội dung nhạy cảm lên LLM; API key chỉ đọc từ env | Whitelist dữ liệu gửi đi |
| NFR-9 | **AI chi phí**: giới hạn số request AI mỗi lần chạy (`max_requests`) | Mặc định 10 |

### 2.4 Tiêu chí chấp nhận (Acceptance criteria)

- **AC-1**: Với repo Node mẫu thiếu SDK + `node_modules`, `--mode=flat` liệt kê ≥ 1 lỗi; `--mode=dep` xác định root cause `node.sdk.version` và đánh dấu `node.deps.installed`, `node.build.ready` là `caused_by`.
- **AC-2**: Output JSON khớp schema 1.0; `summary`, `checks`, `diagnosis` đúng cấu trúc.
- **AC-3**: `--fix` backup file trước khi sửa, rollback thao tác reversible khi bước sau lỗi và ghi rõ thao tác non-reversible; sau khi fix phải chạy lại checks, xuất report/exit code của trạng thái cuối; log ghi rõ mọi thay đổi.
- **AC-4**: `setup-doctor study` nhận ground truth JSON, xuất CSV/JSON với precision, recall, accuracy (tính trên universe `expected_failures ∪ expected_passes`), clarity đúng.
- **AC-5**: Chạy check 2 lần trên cùng repo không làm thay đổi gì trên repo (mtime git status sạch nếu không có `--fix`).
- **AC-6**: Với repo không phải ecosystem hỗ trợ, exit code 0 + message "no supported ecosystem detected".
- **AC-7**: Bật `--ai` với repo Node thiếu SDK: phần remediation có gợi ý của AI; khi tắt mạng/không có key → kết quả vẫn đầy đủ với lệnh viết tay (không crash, exit code đúng).
- **AC-8**: Chạy `study` 2 lần trên cùng dữ liệu → 2 kết quả giống hệt nhau (deterministic, không có AI trong research).
- **AC-9**: Report JSON luôn có `diagnosis.ai_explanation` (null khi tắt `--ai`, string khi bật) — **một schema duy nhất** cho cả hai trường hợp, không có field `ai` riêng; không vi phạm schema 1.0.
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
| **Research Harness** (`study/runner.py`, `study/metrics.py`) | Đọc list repo + ground truth, chạy cả 2 mode mỗi repo, tính metrics, xuất CSV/JSON | Engine, Output |
| **Context** (`context.py`) | `CheckContext`: repo path, OS, config tool, kết quả check đã chạy (để checker khác đọc) | — |
| **AI Provider** (`ai/provider.py`) | Interface trừu tượng gọi LLM (OpenAI/Anthropic); quản lý API key (env), model, timeout, retry; trả output đúng schema | Config |
| **AI Remediation** (`ai/remediation.py`) | Dùng `CheckResult` + evidence → LLM gợi ý lệnh sửa; hợp nhất với remediation viết tay (ưu tiên viết tay); fallback khi lỗi | AI Provider, Output |
| **AI Explainer** (`ai/explainer.py`) | Dùng `diagnosis.root_causes` → LLM viết giải thích tự nhiên; fallback về mô tả rule-based | AI Provider, Engine |

### 3.3 Luồng dữ liệu (Data flow)

1. CLI nhận lệnh → Registry phát hiện ecosystem → chọn checker.
2. Mỗi checker chạy, ghi kết quả vào `CheckContext` → trả `list[CheckResult]`.
3. Engine nhận `list[CheckResult]` → nếu `flat`: sắp xếp theo nhóm; nếu `dep`: dựng DAG, gom root cause.
4. *(Tùy chọn)* Nếu `--ai`: AI Remediation gợi ý lệnh sửa cho check fail; AI Explainer viết giải thích root cause — cả hai độc lập, có fallback, không ảnh hưởng logic chẩn đoán.
5. Nếu `--fix`: Fixer đọc report, backup file, áp dụng remediation trong whitelist, cập nhật log; sau đó chạy lại bước 1-4 để lấy trạng thái cuối.
6. Output report cuối → text ra terminal, JSON ra file/stdout, exit code theo report cuối.
7. Nếu `--study`: Harness lặp các bước check (1-4, luôn tắt AI và không chạy fixer) trên nhiều repo, đối chiếu ground truth, xuất bảng metrics.

### 3.4 Kiến trúc hướng đơn vị nhỏ, tách bạch

- Mỗi checker là một đơn vị độc lập: rõ mục đích, interface (`run(ctx) -> list[CheckResult]`), phụ thuộc duy nhất là `CheckContext`.
- Engine tách khỏi checkers: engine chỉ làm việc trên `CheckResult` (không đọc file, không chạy lệnh) → dễ test bằng fixture `CheckResult`.
- Fixer tách khỏi engine: engine chỉ chẩn đoán, fixer chỉ sửa — không trộn trách nhiệm.
- Codebase hiện mới ở giai đoạn tài liệu thiết kế/kế hoạch; chưa có source code để refactor.

### 3.5 Xử lý lỗi

| Tình huống | Xử lý |
|---|---|
| Lệnh không tồn tại | Checker báo `skip` kèm lý do; không coi là lỗi nếu ecosystem không liên quan |
| Repo không phải ecosystem hỗ trợ | "no supported ecosystem detected" + exit 0 |
| **Command timeout (30s)** — lệnh CHECK | `fail` + remediation "tăng timeout / kiểm tra môi trường" |
| **Fix op timeout** (npm ci/mvn/dotnet/docker) | Dùng `timeout` riêng trong `_WHITELIST_OP` (60-300s), KHÔNG ràng buộc bởi NFR-3 |
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
| `node.runtime.present` | Node có trong PATH (chỉ chạy `node --version`) | `node` không chạy được | `winget install OpenJS.NodeJS.LTS` (Windows) | — |
| `node.sdk.version` | Version đối chiếu `.nvmrc`/`engines` | Version cài < yêu cầu | `nvm install 22; nvm use 22` | `node.runtime.present` |
| `node.pkgmgr.present` | npm/yarn/pnpm hiện diện (chỉ `which`) | Thiếu package manager | `corepack enable` (Windows) | `node.runtime.present` |
| `node.lockfile.exists` | Có lockfile (`package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`) | Thiếu lockfile | `npm install --package-lock-only` (--fix) | `node.pkgmgr.present` |
| `node.deps.installed` | `node_modules` tồn tại (chỉ stat dir) — **không** chạy npm ci khi check | Thiếu `node_modules` | `npm ci` (--fix) | `node.lockfile.exists`, `node.sdk.version` |
| `node.build.ready` | Build tool trong `package.json` có trong `node_modules/.bin` (chỉ stat) | Thiếu build tool | `npm ci` (--fix) | `node.deps.installed` |

**Ghi chú read-only:** check **không chạy** `npm ci`, `npm install`, build script. Chỉ đọc file + stat dir + chạy `--version` không side-effect. `npm ci`/build chỉ xảy ra khi `--fix`.

**3.7.2 Python (`checkers/python_ck.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `python.runtime.present` | Python trong PATH (chỉ `py --version`) | `python`/`py` không chạy | `winget install Python.Python.3.12` (Windows) | — |
| `python.version` | Version đối chiếu `.python-version`/`pyproject.toml` | Sai version | Cài đúng version qua pyenv/py launcher | `python.runtime.present` |
| `python.env.present` | `.venv` tồn tại (chỉ stat `pyvenv.cfg`) | Thiếu venv | `py -m venv .venv` (--fix) | `python.runtime.present` |
| `python.deps.installed` | Cài đủ theo `requirements.txt` (chỉ so `pip list` trong venv, không cài) | Thiếu thư viện | `pip install -r requirements.txt` (--fix) | `python.env.present` |
| `python.build.ready` | Build/test entry point khai báo trong cấu hình (chỉ đọc config) | Thiếu entry point | Cài lại deps | `python.deps.installed` |

**Ghi chú read-only:** check **không chạy** `pip install`/build; chỉ `pip list` (đọc).

**3.7.3 Java (`checkers/java.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `java.runtime.present` | JDK trong PATH (chỉ `java -version`) | Không có `java` | `winget install EclipseAdoptium.Temurin.21.JDK` (Windows) | — |
| `java.version` | JDK version đối chiếu `pom.xml`/`.sdkmanrc` | Sai major version | `winget install Temurin.<ver>.JDK` | `java.runtime.present` |
| `java.maven.gradle.present` | Maven/Gradle/wrapper hiện diện (chỉ `which`/stat) | Thiếu tool | `winget install Apache.Maven` (Windows) | `java.runtime.present` |
| `java.deps.cached` | Cache `.m2`/gradle cache tồn tại (chỉ stat dir) — **không** chạy `mvn dependency:resolve` khi check | Cache rỗng/thiếu | `mvn dependency:resolve` (--fix) | `java.maven.gradle.present` |
| `java.build.ready` | Build file (`pom.xml`/`build.gradle`) hiện diện | Thiếu file | Kiểm tra lại nội dung repo | `java.deps.cached` |

**Ghi chú read-only:** check **không chạy** `mvn dependency:resolve`/`mvn compile` (lệnh này tải deps + ghi cache → side-effect). MVP chỉ kiểm tra sự hiện diện build file và stat cache. Việc resolve chỉ xảy ra khi `--fix`.

**3.7.4 .NET (`checkers/dotnet_ck.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `dotnet.runtime.present` | `dotnet` trong PATH (chỉ `dotnet --list-sdks`) | Không tìm thấy | `winget install Microsoft.DotNet.SDK.8` (Windows) | — |
| `dotnet.sdk.version` | `global.json`/SDK yêu cầu khớp `dotnet --list-sdks` | Thiếu SDK version | `winget install Microsoft.DotNet.SDK.<ver>` | `dotnet.runtime.present` |
| `dotnet.restore.ready` | NuGet cache (`~/.<nuget>/packages`) tồn tại (chỉ stat) — **không** chạy `dotnet restore` khi check | Cache thiếu | `dotnet restore` (--fix) | `dotnet.sdk.version` |
| `dotnet.build.ready` | Project file (`*.csproj`/`*.sln`) hiện diện ở repo root | Thiếu file | Kiểm tra lại nội dung repo | `dotnet.restore.ready` |

**Ghi chú read-only:** check **không chạy** `dotnet restore`/`dotnet build` (có thể tải package + ghi disk). MVP chỉ kiểm tra project file ở repo root và stat cache. Restore chỉ xảy ra khi `--fix`.

**3.7.5 Services (`checkers/services.py`)**

| check_id | Mô tả | Fail khi | Remediation (VD) | depends_on |
|---|---|---|---|---|
| `services.container.present` | Docker daemon reachable (chỉ `docker info`) | Docker không chạy | Khởi động Docker Desktop (--fix) | — |
| `services.compose.up` | `docker compose ps` đọc trạng thái (chỉ đọc, không up) | Container chưa chạy | `docker compose up -d` (--fix) | `services.container.present` |
| `services.db.port` | Port PostgreSQL 5432 mở khi compose có service `db` (TCP probe) | Port đóng | `docker compose up -d db` (--fix) | `services.compose.up` |
| `services.redis` | Redis port (6379) mở (TCP probe) | Không kết nối | `docker compose up -d redis` (--fix) | `services.compose.up` |
| `services.envfile` | `.env` tồn tại; nếu không → từ `.env.example` (chỉ stat) | Thiếu `.env` | Tạo từ template (--fix) | — |

**Ghi chú read-only:** TCP probe/với `docker info`/`compose ps` là đọc, không side-effect; khởi động service chỉ xảy ra khi `--fix`.

**3.7.6 Registry/credentials (`checkers/registry.py`) — chạy khi có dấu hiệu thật sự cần**

| check_id | Mô tả | Fail khi | Mức độ | Remediation (VD) | depends_on |
|---|---|---|---|---|---|
| `registry.git.user` | `git config user.name/email` có (chỉ đọc) | Chưa cấu hình | **warning** | `git config --global user.name ...` | — |
| `registry.git.ssh` | SSH key tồn tại (chỉ stat `~/.ssh`) — **skip khi remote là HTTPS** | Thiếu key + remote SSH | **warning** | `ssh-keygen` + thêm vào GitHub | — |
| `registry.npm` | npm registry trỏ đúng (chỉ đọc config) — chỉ khi repo có `.npmrc` | Sai registry | error | `npm config set registry ...` | `node.runtime.present` |
| `registry.pypi` | File cấu hình pip (`pip.conf`/`pip.ini`) hiện diện — chỉ khi repo có file cấu hình | Thiếu file khi đã khai báo registry | error | Kiểm tra lại index thủ công | `python.runtime.present` |

**Quy ước:** registry checker chỉ chạy khi repo là git repo **và** có ít nhất một trong: `.npmrc`, `pip.conf`/`pip.ini`, hoặc remote git. Git user/SSH là **warning** (không chặn build); chỉ `registry.npm`/`registry.pypi` là error khi repo khai báo registry riêng.

**Quy ước chung:** check `skip` khi ecosystem không liên quan; remediation có OS-specific variant (mặc định Windows); tuyệt đối không tự sửa credentials.

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
- **Redaction trước khi gửi:** evidence được đưa qua bộ lọc `sanitize()` — loại bỏ path tuyệt đối (thay bằng `<path>`), URL registry (thay bằng `<url>`), chuỗi giống secret/token, biến môi trường. Chỉ gửi `check_id`, message đã lọc, OS. Không gửi file repo, credentials, biến môi trường.
- **Quota chung:** `max_requests` áp dụng cho **toàn bộ** AI requests của một lần chạy (remediation + explainer cộng dồn, không phải riêng remediation). Khi hết quota → dừng mọi gọi AI, fallback rule-based.
- **Validate schema:** output của LLM được kiểm tra đúng schema (danh sách `{step, command}` / `{explanation}`) trước khi hiển thị; sai/malformed → bỏ qua, dùng rule-based.
- AI không bao giờ quyết định `status`/`severity` — chỉ dùng cho nội dung remediation/explanation.

### 3.10 Thiết kế Fixer (an toàn, transaction)

`--fix` chỉ áp dụng remediation thỏa **tất cả**: `safe_fix=true` + `source=manual` + **thuộc whitelist operation** dưới đây.

**Whitelist operation (cú pháp argv, không chuỗi tự do):**

| Op | Ví dụ argv | Ghi chú |
|---|---|---|
| `install-node-deps` | `npm ci` / `yarn install --frozen-lockfile` | Chạy trong repo |
| `create-venv` | `py -m venv .venv` | Tạo .venv |
| `install-python-deps` | `pip install -r requirements.txt` | Trong venv |
| `resolve-java-deps` | `mvn dependency:resolve` | Có thể tải cache (đã nói rõ không read-only — chỉ khi `--fix`) |
| `restore-dotnet` | `dotnet restore` | Có thể tải package — chỉ khi `--fix` |
| `start-service` | `docker compose up -d` | Khởi động service — chỉ khi `--fix` |
| `create-env` | Python code copy `.env.example` → `.env` (không dùng shell `copy`) | Copy nội dung file |
| `set-git-identity` | `git config --global user.name ...` | **Không** an toàn mặc định — chỉ in lệnh cho người dùng tự chạy |

**Quy tắc an toàn:**

1. **Backup transaction-level:** trước khi chạy *bất kỳ* lệnh nào, backup **toàn bộ** các file sẽ bị ảnh hưởng (khai báo trong `files` của step) vào `.setup-doctor-backup/<timestamp: giờ-phút-giây.microgiây>/` — đủ phân giải vi mô để tránh trùng khi chạy 2 lần nhanh.
2. **Rollback có giới hạn nếu lỗi:** nếu bước N fail → rollback các bước **reversible** đã apply (khôi phục file từ backup). Các bước install/restore/start-service là non-reversible, không hứa khôi phục trạng thái hệ thống và phải ghi rõ trong log.
3. **Không chạy chuỗi tự do:** mọi lệnh là **argv list** (không phải chuỗi có `&&`/shell operator). Nếu cần ghép, dùng nhiều `RemediationStep` riêng.
4. **Không backup thư mục lớn** (node_modules, .venv): các op này không nằm trong danh sách file cần backup; backup chỉ cho file cấu hình nhỏ (`.env`, `package-lock.json`...).
5. **Không sửa credentials tự động:** op `set-git-identity` **không phải** `safe_fix` mặc định.
6. **Log đầy đủ:** ghi mọi lệnh chạy, đường backup, kết quả vào fix log (in ra + lưu file).
7. **Xóa file mới tạo có khai báo:** chỉ xóa file mới tạo khi đó là path file đơn được whitelist (ví dụ `.env`); không quét/xóa thư mục hoặc path ngoài danh sách `files`.

**Ghi chú read-only vs `--fix`:** mọi op trong bảng trên đều **không** chạy trong lúc check; chỉ chạy khi `--fix`. Check chỉ đọc (xem 3.7).

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
| `--fix` | Áp dụng remediation trong whitelist (có backup) | tắt |
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
        "affected_checks": ["node.sdk.version", "node.deps.installed", "node.build.ready"],
        "chain": "node.sdk.version → node.deps.installed → node.build.ready"
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
| `0` | Tất cả check pass; hoặc repo không thuộc ecosystem hỗ trợ (no supported ecosystem) |
| `1` | Có ít nhất 1 check `fail` (severity error) |
| `2` | Lỗi nội bộ tool, **hoặc path repo không tồn tại / không phải thư mục** (lỗi input) |

> **Phân biệt rõ:** repo không hỗ trợ → exit 0 + output đúng format đã chọn (kể cả JSON); path không tồn tại → exit 2 + thông báo lỗi input (không nhầm với "no ecosystem").

### 4.5 Interfaces giữa các khối

```
Checker.run(ctx: CheckContext) -> list[CheckResult]
Engine.diagnose(checks: list[CheckResult], mode: str, repo_path: str, os_name: str) -> Report
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
  "expected_passes": ["node.runtime.present"],
  "expected_root_causes": ["node.sdk.version"],
  "notes": "Thiếu SDK version; node_modules chưa cài"
}
```

> **Universe đánh giá (quantification universe):** `expected_failures ∪ expected_passes`. Mọi metric (TP/FP/FN/TN/accuracy) tính trên **chính universe này**, không phải toàn bộ checks của tool.
>
> **Quy tắc (chốt theo review #7):**
> - **Mọi ID trong ground truth đều thuộc universe** — kể cả khi tool không emit check đó (→ check đó được coi là **FN** nếu nằm trong `expected_failures`, hay **TN** nếu nằm trong `expected_passes` — nhưng tool không emit là dấu hiệu thiếu sót của checker, phải ghi lại như lỗi ground-truth coverage).
> - Tool báo fail cho ID **không có trong ground truth** → **không tính FP** (check chưa được gán nhãn, không phạt tool vì phát hiện thêm).
> - **ID trong ground truth nhưng không thuộc catalog check** (check_id hợp lệ — ví dụ `node.sdk.version` wrong) → **từ chối khi validate ground truth** (báo lỗi rõ tên check không hợp lệ). Điều này đảm bảo universe luôn có ý nghĩa.

### 4.7 Metrics nghiên cứu

Tất cả metrics tính trên **universe nhãn đã gán** = `expected_failures ∪ expected_passes` (xem 4.6).

| Metric | Định nghĩa |
|---|---|
| **precision** | TP ÷ (TP + FP) |
| **recall** | TP ÷ (TP + FN) |
| **accuracy** | (TP + TN) ÷ universe_size (số nhãn đã gán, không phải tổng checks) |
| **f1** | Harmonic mean của precision & recall |
| **clarity** | Dep mode: số root cause khớp `expected_root_causes` ÷ tổng `expected_root_causes` |
| **remediation_order_correct** | (Dep mode, thủ công hoặc bán tự động) Tỷ lệ repo mà thứ tự remediation theo root cause giúp build thành công mà **không phải sửa lại lỗi đã "sửa"**. Ghi chú định tính. |
| **superfluous_steps** | (Dep mode) Số bước remediation mà người nghiên cứu KHÔNG cần làm (dư thừa) khi làm theo thứ tự root-cause — đo thủ công. |
| **time_to_build** | **Metric thủ công ngoài tool** — người nghiên cứu đo bấm giờ theo protocol 5.4; không phải field do harness tính |

> **Quan trọng (theo review #7):** flat và dep dùng **cùng bộ `CheckResult`** nên precision/recall/accuracy/f1 **chắc chắn giống hệt nhau** giữa hai mode — các metric này **không dùng để so sánh** "dep tốt hơn flat". Sự khác biệt chỉ nằm ở: **clarity** (độ chính xác root cause), **remediation_order_correct**, **superfluous_steps**, và đánh giá người dùng (thủ công). Báo cáo nghiên cứu phải nêu rõ điều này để tránh kết luận sai.

Nghĩa của TP/FP/FN/TN (trên universe):
- **TP**: tool báo fail, ground truth gán fail.
- **FP**: tool báo fail, ground truth gán pass.
- **FN**: tool báo pass/skip **hoặc không emit check**, ground truth gán fail (xem quy tắc 4.6 — ID trong GT luôn thuộc universe).
- **TN**: tool không báo fail (pass/skip/không emit), ground truth tường minh gán pass.

> **Lưu ý:** tool báo fail cho check *không nằm trong ground truth* (không được gán nhãn) → không tính vào FP (tránh phạt tool vì phát hiện thêm). Chỉ FP khi ground truth **tường minh** gán pass mà tool báo fail. Chỉ FN khi ground truth **tường minh** gán fail mà tool không báo fail.

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
| **5. `--fix` có kiểm soát** | Backup `.setup-doctor-backup/<ts>/`, whitelist `safe_fix`, log mọi thay đổi, rollback thao tác reversible, re-check sau fix | AC-3, AC-5 pass |
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
