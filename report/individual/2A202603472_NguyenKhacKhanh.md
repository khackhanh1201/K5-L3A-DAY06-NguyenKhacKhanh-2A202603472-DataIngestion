# Báo cáo cá nhân — Day 6

**Học viên:** Nguyễn Khắc Khánh · **MSSV:** 2A202603472 · **Lớp:** L3A 

> **Sử dụng AI (theo RULES.md):** Claude (Claude Code) được dùng để viết code pipeline trong `starter/src/`, soạn nháp 20 câu benchmark từ text nguồn và gợi ý nhãn audit (coherence, grounding) theo đúng thang điểm trong GUIDE.md. Metadata được kiểm tra bằng script. Evidence được kiểm tra tự động bằng `python -m src.run check`.
> - [X] Tôi đã đọc lại 20 câu hỏi và đối chiếu đáp án với PDF.
> - [X] Tôi đã xem lại từng nhãn coherence/grounding trong `starter/results/audit_*.csv` và sửa nếu không đồng ý.
>
> Người chấm nhãn: AI gợi ý + tác giả xác nhận. Tác giả cũng là người viết benchmark, nên có nguy cơ thiên lệch.

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** Thiên văn học nhập môn, nguồn là OpenStax *Astronomy 2e* (Fraknoi, Morrison, Wolff et al.), giấy phép **CC BY 4.0**, truy cập ngày 2026-11-13. File `astronomy-2e_-_WEB.pdf` có 1151 trang vật lý, PDF CreationDate 2026-04-20. Corpus gồm 2 tài liệu trong [manifest](../../starter/data/manifest.json):
  - `astronomy2e-ch03` (*Orbits and Gravity*): PDF trang 85–109, 25 trang, 64.492 ký tự.
  - `astronomy2e-ch04` (*Earth, Moon, and Sky*): PDF trang 117–147, 31 trang, 84.080 ký tự.

  Tổng **56 trang nội dung**. Quy tắc tính: dùng **số trang vật lý của PDF** (không phải số in trên trang; ví dụ PDF trang 86 in số "68"). Mỗi chương tính từ trang mở đầu đến hết section cuối; bỏ Key Terms, Summary, For Further Exploration, Collaborative Group Activities và Exercises (trang 110–116, 148–156). Trang dưới 200 ký tự bị loại và ghi log, nhưng không có trang nào như vậy ([ingest_errors.json](../../starter/results/ingest_errors.json) rỗng). PDF không được commit vì nặng 163 MB; README ghi link tải.

- **Chuẩn hóa, lỗi và giới hạn:** Dùng pypdf 6.21.4 để đọc từng trang. Chuẩn hóa gồm: Unicode NFC; thay ligature (ﬁ→fi…); bỏ soft hyphen và ký tự zero-width; nối từ bị gạch nối cuối dòng; gộp khoảng trắng; giữ xuống dòng để làm tín hiệu đoạn văn. Không dùng OCR vì mọi trang đều trích xuất được text. Các giới hạn quan sát được:
  1. **Header/footer lọt vào text**, ví dụ "68 3 • Orbits and Gravity / Access for free at openstax.org". Một số chunk chỉ còn lại footer (A, q17 hạng 2: `"piter 5.20 11.86 0.05 Table 3.2 84 3 • Orbits and Gravity Access for free at openstax.org"`).
  2. **Công thức toán bị mất** (trang 90, 91, 97, 100), ví dụ `"squared, or , is , and…"`.
  3. **Thứ tự trích xuất bị lệch**: danh sách *Learning Objectives* rơi xuống cuối trang (trang 86, 91…).
  4. Bảng (Table 3.1, 3.2) bị trải phẳng thành dòng chữ.

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  - **Embedding:** `intfloat/multilingual-e5-small` chạy local qua sentence-transformers 5.7.0 / torch 2.15.0, CPU, **384 chiều**. Thêm tiền tố `query: ` cho câu hỏi và `passage: ` cho chunk theo model card; vector được chuẩn hóa L2.
  - **Vector store:** **Chroma 1.5.9** `PersistentClient`, lưu tại `starter/chroma_db/`, mỗi index một collection (`chunks_A`, `chunks_B`), metric **cosine**, index HNSW (**tìm gần đúng**). Không dùng pgvector vì Docker Desktop cần WSL2 mà máy (Windows 11 Home) chưa cài; Chroma là lựa chọn được phép trong docs/README.md.
  - **Môi trường:** Python 3.12.3.
  - **Lệnh chạy:** `python -m src.run all`, trong thư mục `starter/`.
  - **Chi phí:** **0 USD**. Thời gian load model 18,8s.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** Mỗi chunk có `document_id`, `source` (đường dẫn PDF), `page` (số trang vật lý, int) và `content_hash`. Trường lọc bổ sung là **`chapter`** (string, giá trị "3" hoặc "4"), lấy từ manifest theo khoảng trang của chương, và khớp với tiêu đề chương in trong PDF. Lý do chọn: hai chương dùng chung nhiều từ vựng (orbit, Moon, angular momentum, ellipse), nên khi người dùng nói rõ đang đọc chương nào thì filter giúp loại nhiễu từ chương kia. Cấu hình A còn có thêm `char_start` để truy vết vị trí trong trang.

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C):** Cả ba dùng cùng corpus, cùng model, cùng store, cùng metric, top-k = 3 ([config.json](../../starter/results/config.json)).
  - **A:** `fixed_size` 500 ký tự, overlap 50, chunk trong phạm vi một trang, không filter.
  - **B:** `by_paragraph` tối đa 800 ký tự. Gom nguyên các đoạn văn trong một trang; đoạn quá dài thì cắt ở cuối câu. Dòng trống hoặc dòng kết thúc bằng `.!?:` được coi là hết đoạn. Không filter.
  - **C:** **dùng lại đúng index B** (cùng chunk, cùng vector) và chỉ thêm `where={"chapter": …}` cho các câu có filter. Đây là **khác biệt duy nhất giữa B và C**.
  - Như vậy A–B chỉ thay cách chunk, B–C chỉ thay filter.
- **≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:** Có 20 câu trong [questions.json](../../starter/benchmark/questions.json): **15 dev (q01–q15) / 5 test (q16–q20)**, chốt trước khi chạy.
  - **Loại câu:** 5 trực tiếp, 6 diễn đạt lại, 5 điều kiện/ngoại lệ, 4 metadata filter. Câu filter là q14, q15 (dev) và q16, q17 (test), với giá trị filter nằm trong ngữ cảnh câu hỏi ("In the chapter on…").
  - **Chia theo trang/chủ đề:** test dùng trang 101, 103 (section 3.4), 121, 142, 144; không câu dev nào dùng các trang này. Rủi ro rò rỉ còn lại: dev và test chung 2 chương và từ vựng.
  - **Kiểm chứng evidence:** mỗi `evidence_quote` được copy từ text đã chuẩn hóa, rồi `python -m src.run check` xác nhận quote nằm nguyên văn ở trang gold và giá trị filter tồn tại trong metadata. Câu q04 chấp nhận 2 gold (trang 95 và trang 88).
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test** (ghi trong [benchmark/README.md](../../starter/benchmark/README.md)): (1) dev Evidence Hit@3 cao nhất → (2) dev Hit@1 → (3) dev filter compliance → (4) ít chunk hoặc ingest nhanh hơn. Sau khi chạy không thay đổi tham số nào. Kết quả test được in ra cùng lần chạy với dev nhưng không được dùng để chỉnh cấu hình.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 4/15 | 7/15 | 353 | ingest 17,3s (embed 16,7s); 20 query 0,08s | 0 |
| A | test | 2/5 | 2/5 | 353 | | 0 |
| B | dev | 6/15 | 8/15 | 265 | ingest 15,6s (embed 15,1s); 20 query 0,08s | 0 |
| B | test | 2/5 | 2/5 | 265 | | 0 |
| C | dev | 6/15 | **9/15** | 265 (dùng chung B) | không ingest thêm; 20 query 0,10s | 0 |
| C | test | 2/5 | 2/5 | 265 | | 0 |

Độ dài chunk: A có min 52 / median 500 / max 500 ký tự (tổng 163.322, vì overlap làm trùng khoảng 10%). B có min 38 / median 588 / max 800 (tổng 148.519).

**Nạp lại:** chạy `all` 2 lần, số dòng trong store là 0→353 / 0→265 ở lần 1, rồi 353→353 / 265→265 ở lần 2, không bị nhân đôi ([ingest_runs.jsonl](../../starter/results/ingest_runs.jsonl)). Chunk ID có dạng `doc:p{page}:{cấu hình}:{idx}` và luôn giống nhau giữa các lần chạy. Khi tài liệu thay đổi, `upsert` xóa các chunk cũ của `document_id` đó không còn xuất hiện, rồi ghi đè phần còn lại.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | **0,9** (n=10; 0/1/2 = 1/9/0) | 15/15 | dev 0/2 · test 2/2 (không áp filter) | 2/0/3 → **1,2** |
| B | **1,8** (n=10; 0/1/2 = 0/2/8) | 15/15 | dev 0/2 · test 1/2 (không áp filter) | 1/1/3 → **1,4** |
| C | **1,8** (n=10, cùng chunk với B) | 15/15 | dev **2/2** · test **2/2** | 1/1/3 → **1,4** |

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**
- **Trace đầy đủ** (câu hỏi, ID, text, score, metadata của top-3, cờ hit): [traces.jsonl](../../starter/results/traces.jsonl). Metric tổng hợp: [summary.json](../../starter/results/summary.json). Tổng hợp audit: [audit_summary.json](../../starter/results/audit_summary.json).
- **Coherence** ([audit_coherence.csv](../../starter/results/audit_coherence.csv)): 10 vị trí được cố định **trước khi xem điểm**. Mỗi vị trí là câu bắt đầu gần giữa trang, lấy ở 10 trang đầu sau khi sắp theo (document_id, page). Với mỗi strategy, chấm chunk chứa câu đó. Hạn chế: cả 10 vị trí đều thuộc chương 3 (trang 85–94).
- **Metadata** ([audit_test_hits.csv](../../starter/results/audit_test_hits.csv)): 5 câu test × top-3 × 3 strategy = 45 bản ghi. Mỗi bản ghi được kiểm tra bằng script: text của chunk phải có nguyên văn trong text trang được ghi, `source`, khoảng trang và `chapter` phải khớp manifest. Kết quả 45/45 đúng.
- **Grounding** ([audit_grounding.csv](../../starter/results/audit_grounding.csv)): 5 câu test × 3 strategy, chấm dựa trên **cả top-3**, có ghi lý do.

## Phân tích và kết luận

- **So sánh A–B (thay cách chunk):**
  - B tốt hơn A trên dev: Hit@1 4→6/15, Hit@3 7→8/15. Coherence tăng gấp đôi (0,9→1,8), dùng ít chunk hơn 25% (353→265) và ingest nhanh hơn (17,3→15,6s, vì phải embed ít chunk hơn).
  - Chunk cố định của A thường bắt đầu và kết thúc giữa từ (`"l at any one time…"`, `"…through s"`). Ở 4 trường hợp, A lấy được đúng trang gold nhưng quote bị cắt khỏi chunk (dev q04, q06, q08; test q20).
  - Trên test, A và B bằng nhau (2/5), và A còn thắng B ở q16 (xem lỗi 2). Nghĩa là chunk lớn theo đoạn văn cũng có thể làm loãng tín hiệu.
- **So sánh B–C (chỉ thay filter):**
  - Filter giúp tuân thủ phạm vi tuyệt đối: dev 0/2→2/2, test 1/2→2/2. Ở q17 cấu hình B, hạng 2 là chunk chương 4 (trang 120, về celestial pole); C loại bỏ được chunk này.
  - Filter cứu được q15 (dev Hit@3 8→9/15). Ở B, hạng 3 là chunk chương 3 trang 97 (trọng lực, Moon cách 60 bán kính Trái Đất, score 0,868). C loại chunk này, nên chunk gold trang 141 ("moving away by 3.8 centimeters per year", score 0,865) lên hạng 3. Nhưng filter **không** cứu được q14 và q16, vì nhiễu cùng chương vẫn xếp hạng cao hơn.
  - Test Hit không đổi (2/5). Chỉ có 4 câu filter nên chênh lệch 1 câu chưa đủ ý nghĩa thống kê.
- **Hai ví dụ sai, có ID câu và nguồn:**
  1. **q14, cấu hình C (filter đúng nhưng vẫn trượt).** Gold là `astronomy2e-ch04` trang 140 (angular momentum của hệ Earth–Moon). Filter `chapter=4` hoạt động đúng, nhưng top-3 là trang 138 (lực thủy triều, 2 chunk) và trang 120 (con lắc Foucault). Từ "tidal friction / Earth's spin" trong câu hỏi khớp mạnh với trang 138. Filter chỉ thu hẹp phạm vi, không sửa được lỗi xếp hạng của model 384 chiều.
  2. **q16, cấu hình B và C (đúng trang nhưng sai chunk).** Gold là `astronomy2e-ch04` trang 121, câu "its distance from the Sun varies by only about 3%". B và C lấy được **hai chunk khác nhau của chính trang 121** (đoạn mở đầu về mùa và đoạn "The Seasons and Sunshine"), nhưng không lấy chunk chứa câu 3%. Grounding = 0. Ngược lại, A lấy được cửa sổ 500 ký tự chứa câu này ở hạng 1. Chunk theo đoạn dài 800 ký tự đã làm loãng câu ngắn chứa con số.
  3. Thêm một trường hợp cho thấy chỉ số tự động lệch so với chấm tay: ở **q20**, Hit@3 tự động bằng 0 cho cả 3 cấu hình. Tuy vậy A có evidence bị tách qua 2 chunk cùng trang 144, còn B/C lấy được **bằng chứng tương đương** ở trang 145. Khi chấm tay, cả ba đều đạt grounding 2. Vì vậy Evidence Hit@3 (yêu cầu khớp nguyên văn trong một chunk) đánh giá thấp chất lượng thật.
  - Các câu dev trượt ở **cả ba** cấu hình (q01, q04, q06, q07, q13) cho thấy nút thắt chính nằm ở khả năng xếp hạng của embedding (nhiều đoạn Kepler/ellipse gần nghĩa nhau). Cách chunk hay filter đều không giải quyết được.
- **Chiến lược chọn, đánh đổi, điều kiện áp dụng:**
  - **Chọn C** theo quy tắc đã chốt: dev Hit@3 cao nhất (9/15), Hit@1 bằng B (6/15), filter compliance 2/2.
  - **Đánh đổi:** C không tốn thêm chi phí ingest so với B, coherence 1,8 so với 0,9 của A. Đổi lại, chunk theo đoạn có thể làm loãng các câu ngắn chứa con số (q16), và filter chỉ có tác dụng khi người dùng hoặc ngữ cảnh cung cấp chương.
  - **Điều kiện áp dụng:** tài liệu có cấu trúc đoạn rõ ràng và metadata phạm vi đáng tin. Nếu câu hỏi không có filter thì C giống hệt B.
  - Kết luận chỉ đúng cho corpus này và benchmark 20 câu; **không** tuyên bố C là chiến lược tốt nhất nói chung.
- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:**
  - **Test quá nhỏ:** chỉ 5 câu (thêm/bớt 1 câu là thay đổi 20 điểm phần trăm) và chỉ 4 câu filter. Ba cấu hình bằng nhau trên test.
  - **Nhiễu từ trích xuất PDF:** header/footer, công thức bị mất và thứ tự Learning Objectives bị lệch.
  - **Metadata thô:** `chapter` chỉ có 2 giá trị và không có `section`. `page` là trang vật lý, khác với số in trên trang, nên người dùng có thể nhầm khi tra sách giấy.
  - **Nhãn:** coherence và grounding do AI gợi ý rồi tác giả xác nhận, tác giả cũng là người viết benchmark. Mẫu coherence chỉ thuộc chương 3. Metadata được kiểm tra bằng script dựa trên chính text đã trích xuất, nên không phát hiện được lỗi nếu pypdf đánh số trang sai.
  - **Đo thời gian/chi phí:** thời gian đo một lần trên CPU laptop, gồm cả embed và ghi vào Chroma. HNSW là tìm gần đúng; với khoảng 300 vector thì gần như chính xác, nhưng không đảm bảo. Câu đã có từ câu hỏi đến giờ là chi phí 0 vì model chạy local.
- **Nếu làm lại hoặc mở rộng, cải tiến gì?**
  1. Loại header/footer và dòng "Access for free at openstax.org" khi chuẩn hóa.
  2. Thêm metadata `section` (ví dụ "4.2 The Seasons") lấy từ outline của PDF để lọc chi tiết hơn.
  3. Thử chunk theo câu với cửa sổ khoảng 300–500 ký tự, kết hợp với ngữ cảnh đoạn, để giữ được câu ngắn chứa số liệu như q16.
  4. Thử model lớn hơn (e5-base/large) hoặc hybrid BM25 + dense, cùng một re-ranker cho các câu Kepler/ellipse gần nghĩa nhau.
  5. Mở rộng test lên ≥15 câu và thêm định nghĩa hit đa chunk để đo các trường hợp evidence bị tách (q20).
