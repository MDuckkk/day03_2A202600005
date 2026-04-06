# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: Z1
- **Team Members**: Bùi Minh Đức, Hoàng Quang Thắng, Trần Thanh Nguyên, Vũ Văn Huân, Lê Nguyễn Chí Bảo, Nguyễn Phan Tuấn Anh
- **Deployment Date**: 06-04-2026

---

## 1. Executive Summary

*Brief overview of the agent's goal and success rate compared to the baseline chatbot.*

- **Success Rate**: 86.7% on 15 logged agent sessions (13/15 ended with `final_answer`; 2/15 hit `max_steps_reached`).
- **Key Outcome**: On 6 paired prompts where both systems were run, the agent produced grounded, store-specific outputs in 3/6 cases while the baseline chatbot achieved 0/6, showing a +50 percentage-point improvement thanks to tool usage (`search_product`, `get_product_detail`, `compare_product`, `check_inventory`).

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
*Diagram or description of the Thought-Action-Observation loop.*

### 2.2 Tool Definitions (Inventory)
| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `calc_tax` | `json` | Calculate VAT based on country code. |
| `search_api` | `string` | Retrieve real-time information from Google Search. |

### 2.3 LLM Providers Used
- **Primary**: Gemma 4
- **Secondary (Backup)**: Gemini 3.0-flash preview, 4o mini

---

## 3. Telemetry & Performance Dashboard

*Analyze the industry metrics collected during the final test run.*

- **Average Latency (P50)**: 43,069.6 ms (from 14 valid `AGENT_START` -> `AGENT_END` sessions in `logs/2026-04-06.log`).
- **Max Latency (P99)**: 118,547.1 ms.
- **Average Tokens per Task**: N/A in current run (`LLM_METRIC` events were not logged, so token usage is unavailable from telemetry).
- **Total Cost of Test Suite**: N/A in current run (cost estimate is derived from token logs, which are missing in this log file).

---

## 4. Root Cause Analysis (RCA) - Failure Traces

*Deep dive into why the agent failed.*

### Case Study: Max-Step Exhaustion on Missing Product Attributes
- **Input**: "vay thi dell xps 13 va macbook air con nao nhe hon"
- **Observation**: The agent consumed all 5 steps (`max_steps_reached`) after calling `search_product` -> `search_product` -> `get_product_detail` -> `get_product_detail` -> `web_search_product`. Internal DB tools returned price/spec/stock but no weight field, and web search returned noisy snippets that did not provide a reliable direct comparison. The final output also leaked intermediate reasoning text (`Thought:` and an unfinished `Action:`), showing weak termination quality under uncertainty.
- **Root Cause**: The toolset is missing a structured source for weight/thickness attributes, forcing the agent to rely on low-quality web snippets. In parallel, the prompt/parser policy does not strictly enforce a clean "Final Answer only" response when the loop hits `max_steps`, so formatting degrades at failure boundaries.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2
- **Diff**: Prompt v2 bổ sung các ràng buộc rõ ràng trong system prompt: bắt buộc format Thought -> Action -> Observation, trả lời cùng ngôn ngữ người dùng, hạn chế nêu đối thủ, và nhấn mạnh dùng quan sát thay vì suy đoán theo knowledge cutoff.
- **Result**: Với telemetry hiện có trong `logs/2026-04-06.log`, chưa thể so sánh trực tiếp v1 vs v2 vì log không gắn nhãn version theo từng phiên chạy. Tuy nhiên, ở cấu hình prompt hiện tại (v2), tỉ lệ lỗi gọi tool dạng runtime là 0/23 `TOOL_RESULT` có chuỗi lỗi; đồng thời vẫn còn 2/19 phiên `AGENT_END` rơi vào `max_steps_reached` (10.5%), cho thấy chất lượng gọi tool ổn nhưng cần cải thiện chính sách kết thúc vòng lặp.

### Experiment 2 (Bonus): Chatbot vs Agent
| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Store-grounded QA (8 cặp prompt trong log) | 2/8 grounded (25.0%) | 3/8 grounded (37.5%) | **Agent** |
| Multi-step inventory/price lookup | Thường hỏi lại hoặc trả lời chung chung, thiếu dữ liệu kho | Có xu hướng gọi tool kho nội bộ và trả lời theo ID/giá/tồn kho | **Agent** |

- **Evaluation setup**: Trích 8 cặp hội thoại theo chuỗi `CHATBOT_START -> CHATBOT_END -> AGENT_START -> AGENT_END` cùng input trong `logs/2026-04-06.log`.
- **Key takeaway**: Agent vượt chatbot +12.5 điểm phần trăm ở tiêu chí grounded-to-store trong dữ liệu hiện có; mức cải thiện nhỏ hơn kỳ vọng vì một số phiên agent vẫn trả lời tổng quát thay vì chốt từ dữ liệu kho.

---

## 6. Production Readiness Review

*Considerations for taking this system to a real-world environment.*

- **Security**: Đã có một số biện pháp cơ bản: query DB dùng parameterized SQL (giảm rủi ro SQL injection), `read_web_page` có timeout 10s và loại bỏ script/style khi trích xuất nội dung. Tuy nhiên, vẫn còn rủi ro production quan trọng: chưa có allowlist domain cho URL (nguy cơ SSRF), chưa có policy lọc prompt-injection từ nội dung web, và `web_search_product` chưa đặt timeout request nên có thể treo khi mạng chậm.
- **Guardrails**: Agent đã giới hạn vòng lặp `max_steps=5` để chặn loop vô hạn. Dữ liệu từ `logs/2026-04-06.log` cho thấy 2/19 phiên `AGENT_END` rơi vào `max_steps_reached` (10.5%), nghĩa là guardrail hoạt động nhưng vẫn có một phần tác vụ chưa hội tụ. Ngoài ra, log cho thấy 23 lần gọi tool thành công ở mức thực thi (không có chuỗi lỗi runtime trong `TOOL_RESULT`), nhưng chất lượng câu trả lời vẫn có thể lệch dữ kiện nếu observation thiếu.
- **Scaling**: Kiến trúc đã có nền tảng tốt để scale theo chiều ngang chức năng: tách lớp provider (local/openai/gemini), tool độc lập theo module, telemetry JSON có cấu trúc. Để đi production ở lưu lượng cao cần bổ sung: hàng đợi async cho tool I/O, timeout/retry/circuit-breaker thống nhất cho mọi HTTP call, log aggregation tập trung (thay vì file cục bộ), và orchestration state-machine (ví dụ LangGraph) để quản lý nhánh xử lý và fallback rõ ràng hơn.

---

> [!NOTE]
> Submit this report by renaming it to `GROUP_REPORT_[TEAM_NAME].md` and placing it in this folder.
