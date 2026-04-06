# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Bùi Minh Đức
- **Student ID**: 2A202600005
- **Date**: 06-04-2026

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*
Trong lab này, em config DB, crawl data, viết toàn bộ tools, tham gia phát triển và kiểm thử chatbot và agent.

- **Modules Implementated**:
  - `/run_demo.py`
  - `src/tools/check_inventory.py`
  - `src/tools/compare_product.py` 
  - `src/tools/get_product_detail.py`
  - `src/tools/search_product.py`
  - `src/tools/init_db.py`

- **Code Highlights**:
Mỗi tool theo cùng một contract: hàm Python nhận `str`, trả `str`, kèm `TOOL_SPEC` dict gồm `name`, `description`, `func`. Agent chỉ cần đọc `TOOL_SPEC` — không cần biết implementation bên trong.

`init_db.py` — tạo bảng `products` và seed 6 sản phẩm, dùng `INSERT OR IGNORE` để idempotent:
```python
cursor.executemany("""
    INSERT OR IGNORE INTO products (id, name, category, price, stock, specs)
    VALUES (?, ?, ?, ?, ?, ?)
""", products)
```

`compare_product.py` — build `IN (?, ...)` query động từ chuỗi ID cách nhau bởi dấu phẩy, output bảng text có header để LLM dễ parse:
```python
ids = [p.strip() for p in product_list.split(",")]
placeholders = ",".join(["?" for _ in ids])
cursor.execute(f"SELECT id, name, price, specs, stock FROM products WHERE id IN ({placeholders})", ids)
```

`check_inventory.py` — tách riêng khỏi `get_product_detail` để agent gọi nhanh khi chỉ cần biết tồn kho, tiết kiệm token trong scratchpad:
```python
if stock > 0:
    return f"{name}: Còn {stock} sản phẩm trong kho"
return f"{name}: Hết hàng"
```

`read_web_page.py` — strip HTML bằng BeautifulSoup, giới hạn 4000 ký tự để tránh overflow context window local model:
```python
if len(text) > 4000:
    text = text[:4000] + "\n... (nội dung quá dài đã được cắt bớt)"
```

Parse Action từ LLM output trong `agent.py` bằng regex:
```python
def _parse_action(self, text: str) -> tuple:
    match = re.search(r"Action:\s*(\w+)\((.*?)\)", text, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip().strip("'\"")
    return None, None
```

Fallback khi hết `max_steps` — agent tổng hợp Final Answer từ những gì đã quan sát thay vì trả lỗi:
```python
scratchpad += "Thought: I have reached the maximum number of steps. I must give my Final Answer now.\nFinal Answer:"
result = self.llm.generate(scratchpad, system_prompt=system_prompt)
```

- **Documentation**: Agent nhận `user_input`, build `scratchpad` tích lũy qua từng bước. Mỗi lần LLM sinh ra `Action: tool_name(arg)`, agent gọi `_execute_tool()` tra cứu tool trong `self.tools` dict (được build từ `TOOL_SPEC` của từng file), append `Observation: <kết quả>` vào scratchpad. Vòng lặp kết thúc khi LLM sinh `Final Answer:` hoặc đạt `max_steps`.

---

## II. Debugging Case Study (10 Points)

*Agent gọi sai argument vào `search_product` — query ngữ nghĩa thay vì keyword.*

- **Problem Description**: Khi user hỏi *"Tôi muốn mua sản phẩm đắt nhất, còn hàng không?"*, agent gọi `search_product("sản phẩm đắt nhất")` ở step đầu tiên. Tool dùng `LIKE` query nên không match được gì. Agent phải mất thêm 3 steps để tìm workaround (search "Laptop" → compare p004,p005 → check_inventory p005), tốn tổng cộng 5 steps cho một câu hỏi đơn giản.

- **Log Source** (`logs/2026-04-06.log`):
```json
{
  "timestamp": "2026-04-06T10:48:20.669159",
  "event": "TOOL_RESULT",
  "data": {
    "tool": "search_product",
    "args": "sản phẩm đắt nhất",
    "result_preview": "Không tìm thấy sản phẩm nào với từ khóa 'sản phẩm đắt nhất'"
  }
}
```

- **Diagnosis**: `TOOL_SPEC["description"]` của `search_product` chỉ ghi *"tìm kiếm theo tên hoặc danh mục"* nhưng không nêu rõ giới hạn và ví dụ danh mục hợp lệ. LLM không biết tool này không hỗ trợ truy vấn ngữ nghĩa như "đắt nhất", "rẻ nhất". Đây là lỗi **tool spec không đủ rõ ràng**, không phải lỗi của model.

- **Solution**: Cập nhật description để LLM hiểu rõ giới hạn và cách workaround đúng:
```python
TOOL_SPEC = {
    "name": "search_product",
    "description": (
        "Tìm kiếm sản phẩm trong cửa hàng theo tên hoặc danh mục. "
        "Chỉ hỗ trợ tìm theo từ khóa cụ thể. "
        "Danh mục hợp lệ: 'Điện thoại', 'Laptop', 'Máy tính bảng'. "
        "KHÔNG hỗ trợ truy vấn như 'đắt nhất', 'rẻ nhất', 'tất cả'. "
        "Để tìm sản phẩm đắt nhất: search từng danh mục rồi dùng compare_product."
    ),
    "func": search_product
}
```

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1. **Reasoning**: Block `Thought` buộc LLM phải lên kế hoạch trước khi hành động. Với câu hỏi *"Tìm iPhone rồi cho tôi biết còn hàng không và giá bao nhiêu"*, agent sinh chuỗi suy luận: tìm iPhone trước → lấy danh sách ID → kiểm tra từng ID. Chatbot không có bước này nên trả lời ngay bằng kiến thức tĩnh, dẫn đến hallucination (*"Hiện tại tôi không thể kiểm tra tình trạng hàng hóa cụ thể"*).

2. **Reliability**: Agent thực sự kém hơn ở câu hỏi đơn giản không cần tool, ví dụ *"Cửa hàng bán những loại sản phẩm gì?"*. Chatbot trả lời ngay lập tức, còn agent mất thêm 1-2 steps để quyết định không cần dùng tool. Ngoài ra, agent có thể bị lỗi khi tool trả về dữ liệu không như kỳ vọng — case p999/p888 khiến agent leo thang sang `web_search_product` không cần thiết.

3. **Observation**: Observation là yếu tố then chốt. Khi `check_inventory("p002")` trả về *"Hết hàng"*, agent ngay lập tức điều chỉnh Final Answer để phân biệt p001 (còn hàng) và p002 (hết hàng). Nếu không có Observation, LLM sẽ đoán mò. Đây là điểm mạnh cốt lõi của ReAct so với chatbot thuần túy.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Thêm tool `list_all_products()` để tránh agent phải search từng danh mục khi cần tổng hợp toàn bộ catalog. Với hệ thống lớn hơn, dùng vector DB (FAISS, Chroma) để retrieve tool phù hợp thay vì liệt kê tất cả trong system prompt.

- **Safety**: Thêm input validation ở lớp tool — sanitize argument trước khi đưa vào SQL query để tránh injection. Thêm "Supervisor LLM" kiểm tra action trước khi thực thi với các tool có side effect (đặt hàng, thanh toán).

- **Performance**: Implement `PerformanceTracker.track_request()` đầy đủ trong các LLM provider để có token count và cost thực tế. Hiện tại `LLM_METRIC` event chưa được emit, thiếu dữ liệu quan trọng cho monitoring production.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
