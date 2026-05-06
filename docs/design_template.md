# Design Template

## Problem

Hệ thống cần nhận một câu hỏi nghiên cứu dài, tìm nguồn liên quan, rút ra điểm chính, so sánh góc nhìn, và viết câu trả lời cuối cùng có tham chiếu đến nguồn.

## Why multi-agent?

Một single-agent dễ bị quá tải khi phải tìm kiếm, lọc nguồn, phân tích, và viết trong cùng một bước. Chia vai giúp mỗi bước rõ trách nhiệm hơn, dễ debug hơn, và cho phép kiểm tra chất lượng ở từng handoff.

## Agent roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Chọn bước tiếp theo và dừng khi đủ điều kiện | Shared state | Route decision | Kẹt vòng lặp hoặc dừng quá sớm |
| Researcher | Tìm và lọc nguồn, tạo research notes | Query, max_sources | Sources, research notes | Thiếu nguồn hoặc nguồn trùng lặp |
| Analyst | Rút ra claims, trade-offs, và khoảng trống bằng chứng | Sources, research notes | Analysis notes | Diễn giải quá đà hoặc bỏ sót mâu thuẫn |
| Writer | Viết câu trả lời cuối với citations | Research notes, analysis notes, sources | Final answer | Câu trả lời mơ hồ hoặc thiếu tham chiếu |

## Shared state

Shared state nên có query gốc, danh sách nguồn, notes theo từng bước, final answer, lịch sử route, trace, và errors. Các field này giúp supervisor biết còn thiếu gì, đồng thời cho phép benchmark chất lượng và lần theo nguyên nhân khi workflow thất bại.

## Routing policy

Graph đi theo chuỗi `Supervisor -> Researcher -> Supervisor -> Analyst -> Supervisor -> Writer -> Supervisor -> Critic -> Supervisor -> done`, với nhánh quay lại writer nếu critic phát hiện lỗi trích dẫn hoặc bằng chứng yếu.

## Guardrails

- Max iterations:
- Timeout:
- Retry:
- Fallback:
- Validation:

## Benchmark plan

Query mẫu:

- Research GraphRAG state-of-the-art and write a 500-word summary.
- Compare single-agent and multi-agent workflows for customer support.
- Summarize production guardrails for LLM agents.

Metric:

- Latency để đo thời gian chạy.
- Estimated cost để ước lượng chi phí model.
- Quality score để chấm tổng thể.
- Citation coverage để kiểm tra tham chiếu.
- Error rate để đo số case fail.

Expected outcome:

- Multi-agent nên tốt hơn về cấu trúc, khả năng trace, và citation coverage.
- Single-agent thường nhanh hơn nhưng dễ thiếu bước kiểm chứng.
