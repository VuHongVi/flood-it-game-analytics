# 10 câu hỏi phỏng vấn về dự án (kèm gợi ý trả lời)

*Số liệu sinh tự động từ results/metrics.json.*

## 1. Tóm tắt dự án trong 1 phút?

Phân tích dữ liệu Firebase của game Flood-It trên BigQuery: 15,175 người chơi, 114 ngày. Pipeline tự động (SQL có tham số, dry-run chặn chi phí, cache) → tăng trưởng, retention cohort, doanh thu, level, phân khúc, churn model, A/B. Kết luận chính: người chơi rời đi rất nhanh (D1 21.5%), quyết định nằm ở phiên đầu và ở level 27; IAP gần như không có nên đòn bẩy là retention + quảng cáo.

## 2. Retention D7 bạn tính thế nào? Vì sao phải xử lý right-censoring?

Classic Day-N: số người hoạt động đúng ngày cài + 7 chia số người ĐỦ ĐIỀU KIỆN (ngày cài + 7 ≤ ngày cuối dữ liệu). Nếu chia cho tất cả người cài, cohort cuối tháng 9 chưa có ngày thứ 7 sẽ bị tính là rời bỏ → retention bị kéo thấp sai. Kết quả D7 = 5.5% trên 3,986 người eligible, có khoảng tin cậy Wilson.

## 3. Bạn phát hiện vấn đề dữ liệu nào? Làm sao biết?

Không tin, phải query: (1) đúng 50,000 event mỗi ngày → dữ liệu bị lấy mẫu; (2) 60% người chơi cài trước khoảng dữ liệu → cohort chỉ dùng người cài trong khoảng; (3) 29% người mới thiếu first_open; (4) level lưu lẫn int/double; (5) event_value_in_usd NULL ở 3 giao dịch; (6) traffic source google-play chỉ có ở Android.

## 4. DAU có ngày tăng gấp đôi rưỡi, bạn giải thích sao?

7 ngày DAU ~1,229 nhưng install ~1.6, nên không phải người mới. So mix event: screen_view chỉ còn 14.5% so với ngày thường. Vì mẫu cố định 50.000 event/ngày, thiếu screen_view thì ngân sách event chia cho nhiều người hơn (41 vs 107 event/người) → DAU bị thổi phồng. Đây là artifact; tôi đánh dấu và kiểm tra độ nhạy (D1 gần như không đổi).

## 5. ARPU, ARPDAU, ARPPU, LTV khác nhau thế nào? Số của game này?

ARPU = doanh thu / người hoạt động ($0.0021); ARPDAU = doanh thu / tổng DAU ($0.00054); ARPPU = doanh thu / người trả phí ($1.18); LTV D30 = doanh thu cộng dồn 30 ngày / install, cùng một quần thể ($0.0027). Payer rate 0.18%, chỉ 27 giao dịch → số rất nhiễu, chỉ mang tính định hướng; doanh thu quảng cáo không có trong export.

## 6. Mô hình churn: định nghĩa, tránh leakage, kết quả?

Churn = không hoạt động ngày 7–30 sau cài, chỉ trên 2,955 người đủ 30 ngày quan sát. Feature chỉ lấy hành vi NGÀY CÀI → không dùng thông tin tương lai. Logistic regression (log + chuẩn hoá, class_weight balanced) và cây quyết định depth 4; train/test 75/25 phân tầng + 5-fold CV. AUC test 0.68 (CV 0.62). Biến mạnh nhất: thời gian chơi ngày đầu. Nhóm 10% rủi ro cao churn 86.5% vs 51.3%: đủ để xếp hạng, chưa đủ nhắm cá nhân.

## 7. AUC 0.68 có tốt không? Làm sao cải thiện?

Mức trung bình — chỉ có 1 ngày hành vi và dữ liệu bị lấy mẫu. Cải thiện: thêm D1–D3 (dự đoán muộn hơn nhưng chính xác hơn), feature theo phiên (thời gian giữa các phiên, tốc độ qua level, số lần fail liên tiếp), thiết bị/OS, gradient boosting; đánh giá thêm precision@top-decile vì đội CRM chỉ nhắm một nhóm nhỏ.

## 8. iOS vs Android khác biệt có ý nghĩa không? Có phải nhân quả?

D1 iOS thấp hơn +3.8 pp (CI -6.3 pp đến -1.2 pp, p = 0.005), nhưng Cohen's h -0.09 là rất nhỏ; D7 không khác (p = 0.305). Đây là so sánh quan sát: hai nhóm khác về quốc gia, thiết bị, kênh — không phải nhân quả. Với traffic source tôi chỉ so trong Android vì iOS chỉ có (direct).

## 9. Thiết kế A/B test cho thay đổi độ khó level 27?

Giả thuyết: giảm độ khó level 27 tăng tỷ lệ qua level và retention. Random theo user, 50/50. Metric chính: tỷ lệ qua level; metric cấp game: D7; guardrail: lượt xem quảng cáo thưởng, mua extra steps, crash. Cỡ mẫu: baseline D1 21.5%, MDE +2 pp, α 0,05, power 0,8 → 6,834/nhánh; với lượng install trong mẫu (40.3/ngày) mất ~340 ngày → cần chạy trên toàn bộ traffic hoặc chọn MDE lớn hơn; chạy đủ chu kỳ tuần, không peek.

## 10. Bạn dùng AI thế nào và kiểm chứng ra sao?

AI viết nháp SQL/Python, tôi coi là bản nháp phải kiểm chứng: mỗi chỉ số tính 2 cách (SQL trên event thô và Pandas trên bảng player-level), so khớp tự động 32/32 PASS, thêm kiểm tra bất biến và unit test. Các lỗi AI đã bắt được được ghi trong docs/ai_corrections.md, ví dụ alias trong ROLLUP làm dòng tổng NULL, đường LTV đi xuống do đổi quần thể, tỷ lệ người mới bị left-censoring.
