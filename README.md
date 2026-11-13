# Day 06 · Data Ingestion Engineering

> ## Bài làm — Nguyễn Khắc Khánh (2A202603472)
>
> **Corpus:** OpenStax *Astronomy 2e* (CC BY 4.0), Ch.3 + Ch.4, 56 trang nội dung · **Embedding:** `intfloat/multilingual-e5-small` (local, 384d, chi phí 0) · **Vector store:** Chroma 1.5.9 persistent, cosine · **Báo cáo:** [report/individual/2A202603472_NguyenKhacKhanh.md](report/individual/2A202603472_NguyenKhacKhanh.md)
>
> Docker/pgvector không chạy được trên máy (Windows Home chưa có WSL2) nên dùng Chroma — lựa chọn được phép trong [docs/README.md](docs/README.md).
>
> ### Setup và chạy lại (Windows PowerShell, trong thư mục `starter/`)
>
> ```bash
> python -m venv .venv
> .venv\Scripts\Activate.ps1
> python -m pip install -r requirements.txt
> Copy-Item .env.example .env
> ```
>
> Tải PDF (163 MB, không commit vì vượt giới hạn GitHub) từ https://openstax.org/details/books/astronomy-2e và lưu thành `starter/data/raw/astronomy-2e.pdf` (bản dùng: `astronomy-2e_-_WEB.pdf`, 1151 trang, PDF CreationDate 2026-04-20).
>
> ```bash
> python -m src.run ingest   # đọc + chuẩn hoá -> results/pages.jsonl, kiểm tra >= 30 trang
> python -m src.run check    # kiểm chứng evidence của benchmark/questions.json
> python -m src.run all      # chunk, embed, lưu Chroma, chạy A/B/C, metric, file audit
> ```
>
> | Thành phần | Đường dẫn |
> |---|---|
> | Code pipeline | [starter/src/](starter/src/) |
> | Manifest dữ liệu | [starter/data/manifest.json](starter/data/manifest.json) |
> | Benchmark + gold | [starter/benchmark/](starter/benchmark/) |
> | Cấu hình A/B/C, giả thuyết | [artifacts/experiment_log.csv](artifacts/experiment_log.csv), [starter/results/config.json](starter/results/config.json) |
> | Trace top-3, metric, thống kê | [starter/results/traces.jsonl](starter/results/traces.jsonl), [starter/results/summary.json](starter/results/summary.json) |
> | Nhãn audit | [starter/results/audit_*.csv](starter/results/), [starter/results/audit_summary.json](starter/results/audit_summary.json) |
> | Log lỗi ingest, nạp lại | [starter/results/ingest_errors.json](starter/results/ingest_errors.json), [starter/results/ingest_runs.jsonl](starter/results/ingest_runs.jsonl) |

---

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
