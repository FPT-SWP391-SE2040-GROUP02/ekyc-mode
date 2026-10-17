> Ghi chú cũ của bản prototype cục bộ, giữ lại để tham khảo các ca kiểm thử. Một số mục nhắc `.venv` và `models` có sẵn trong thư mục, và các ảnh thử (ví dụ `1791354186872…`) không nằm trong repo này. Hướng dẫn cài và chạy hiện hành ở `README.md`.

# LegacyVault eKYC tích hợp đầy đủ — 0.2.2

Đây là bản tích hợp đầy đủ mới nhất 0.2.2. Môi trường Python `.venv`, trọng số `models` và mã nguồn đều nằm trong thư mục này. Bản này chạy tại **http://127.0.0.1:8879/**. Dùng duy nhất địa chỉ này với START.cmd trong thư mục hiện tại.

Giao diện mới **ui-03** đã áp dụng mẫu LegacyVault được duyệt: thanh điều hướng xanh đậm, nền sáng và ba màn hình Đọc căn cước / So khớp khuôn mặt / Kiểm tra camera. Sau mỗi lần quét thành công, thông tin OCR gốc xuất hiện ngay dưới ảnh ở tab mặt tương ứng. Bảng bên phải chứa thông tin tổng hợp có thể chỉnh sửa; việc sửa bảng không thay đổi kết quả OCR gốc. Có bố cục cho màn hình nhỏ và điều hướng tab bằng bàn phím.

## Mở chương trình

1. Mở `START.cmd` trong thư mục này. Nếu đang chạy bản trước, dừng cửa sổ máy chủ bằng Ctrl+C rồi mở lại START.cmd và tải lại trang. Kiểm tra /api/health trả version 0.2.2.
2. Giữ cửa sổ chương trình chạy. Khi khởi chạy bằng START.cmd, dùng Ctrl+C để dừng.
3. Bản này dùng `.venv` và `models` ngay trong thư mục hiện tại; không cần prototype gốc ở Downloads. Máy hiện tại đã được cài sẵn, không cần chạy setup. Khi chuyển sang máy khác, dùng Python 3.12 x64 và chạy `setup.cmd` để tạo môi trường phù hợp. Các lệnh kiểm tra dùng `.venv\Scripts\python.exe`; không dùng pip.exe cũ sau khi chuyển môi trường.

## Test quét thẻ mới

1. Ở **Đọc căn cước**, chọn tab **Mặt trước**, chọn ảnh rồi bấm **Đọc thông tin**.
2. Kiểm tra số căn cước, tên và ngày sinh. Địa chỉ có thể trống vì nằm ở mặt sau.
3. Chuyển tab **Mặt sau · tùy chọn**, chọn **ảnh mặt sau cùng thẻ**, bấm **Đọc nơi cư trú**. Kết quả và trạng thái đối chiếu số thẻ xuất hiện dưới ảnh mặt sau.
4. Kiểm tra trường **Nơi cư trú / địa chỉ thường trú**. Địa chỉ lấy theo nhãn nơi cư trú trên thẻ; không lấy nhầm nơi đăng ký khai sinh. Hai ảnh mới `1791354186872…` và `1791354224152…` đã đọc đúng nội dung địa chỉ, bỏ qua khác biệt dấu câu.
5. Khi đọc được số căn cước trong MRZ mặt sau, giao diện so với số OCR mặt trước. Khác số thì chặn ghép. Nếu không đọc được số MRZ, giao diện báo chưa đối chiếu được hai mặt; kiểm tra chúng thuộc cùng thẻ. Đây là kiểm tra nhất quán, chưa xác thực thẻ thật/giả.

## Test CCCD cũ

Chọn mặt trước và bấm Đọc thông tin. Nếu có nhãn Nơi thường trú, địa chỉ được điền từ mặt trước; có thể bỏ qua mặt sau. Ảnh `122411.png` đã lấy đúng địa chỉ. Ảnh `122316.png` còn lỗi chữ OCR ở phần cuối địa chỉ; đối chiếu và sửa trường này trước khi dùng.

## Test đổi thẻ và so khớp

- Đọc thẻ A, rồi chọn thẻ B: dữ liệu tên/số/ngày sinh/địa chỉ và mặt sau cũ phải được xóa ngay. Kết quả trả chậm của A không được ghi vào B.
- Chọn lại mặt sau: địa chỉ từng lấy từ mặt sau cũ được xóa; địa chỉ lấy từ mặt trước được giữ. Mặt sau khác số căn cước phải bị từ chối.
- Ảnh tham chiếu được khóa tự động từ lần đọc mặt trước thành công; chỉ chọn selfie trong So khớp mặt. Ba ảnh của thẻ cùng người (`1791349811201…`, `1791349859727…`, `121133.png`) đều so khớp qua ngưỡng với selfie đã xác nhận; ảnh xoay được thử các hướng khi không tìm thấy mặt.
- Chọn Tải kết quả JSON để xuất bốn trường và nguồn mặt trước/mặt sau. Ảnh xem trước không được đưa vào JSON. Ảnh tải lên chỉ xử lý trong bộ nhớ; không trích hoặc lưu dữ liệu vân tay.

## Chạy kiểm thử tự động

Bản sửa tìm mặt `face-scale-01`: ảnh chân dung cận mặt lớn có thể bị YuNet bỏ sót ở độ phân giải gốc. Nếu chưa tìm được mặt, hệ thống thử ảnh thu nhỏ với cạnh dài 640 rồi 320 pixel; ánh xạ hộp và năm điểm mốc về ảnh gốc trước khi SFace căn chỉnh. Không giảm ngưỡng tìm mặt 0,85 hoặc ngưỡng so khớp 0,363, không chọn một mặt từ ảnh nhiều mặt. `Image(1).png` đã tìm được mặt với điểm detector 0,92986; đây không phải điểm so khớp hay xác suất danh tính.

Sau khi cập nhật Python, dừng máy chủ đang chạy bằng Ctrl+C trong cửa sổ START.cmd rồi mở lại START.cmd. `/api/health` của bản đã nạp sửa lỗi có `face_detection_strategy: original_then_640_320`. Chỉ Ctrl+F5 không nạp lại mã Python. Đọc lại mặt trước để tạo tham chiếu mới sau khi khởi động lại, rồi chọn selfie và so khớp.

Test riêng phần này: `.venv\Scripts\python.exe -B test_face_detection.py` (7 bài bảo vệ tọa độ/kích thước/số mặt) và `.venv\Scripts\python.exe -B -X utf8 test_face_detection_real_models.py` (11/11 ca model thật, gồm ảnh người dùng báo lỗi, ba hướng xoay, ảnh trống, hai mặt, và năm cặp danh tính trước đây). Xem `test-results/FACE_SCALE_RESULTS.json`.

Mở `TEST.cmd`. Chương trình chạy kiểm thử tìm mặt nhiều kích thước, logic/API, kiểm thử luồng giao diện bằng Node (nếu có), kiểm thử model thật qua luồng tham chiếu đã khóa, rồi chạy bộ phân loại mặt thẻ và model thật trên bộ ảnh trong thư mục ảnh thử cục bộ (biến `EKYC_TEST_PHOTOS`, không có trong repo). Xem `TEST_RESULTS.json` và `BAO_CAO_V2.md`.

Kiểm thử ảnh trả exit code 1 khi còn kết quả khác ảnh gốc. Hiện còn hai ca OCR sai chữ, được ghi rõ trong báo cáo; không đánh dấu chúng là đã qua. Có thể chạy riêng một ảnh bằng `.venv\Scripts\python.exe` trong thư mục này: `test_supplied_images.py --only 1791349537388`.

## Những gì đã sửa và giới hạn

- Nhãn ngày sinh thẻ mới; sử dụng cả PaddleOCR và VietOCR để nhận nhãn; tìm giá trị cùng hàng bằng vị trí, kể cả khi đứng trước nhãn trong danh sách OCR.
- Không lấy phần tiếng Anh bị đọc sai của nhãn họ tên làm tên người.
- Tự thử xoay ảnh OCR khi chưa đủ dấu hiệu đọc đúng hướng; ảnh hiển thị và khung chữ theo đúng hướng đã chọn. Việc xoay có thể tăng thời gian chạy CPU.
- Ghép địa chỉ nhiều dòng, bỏ nhãn song ngữ và giới hạn trước nơi sinh/ngày cấp/hết hạn; dùng số nhà PaddleOCR và chữ tiếng Việt VietOCR.
- Chặn kết quả cũ, xóa địa chỉ và mặt sau khi đổi mặt trước.

Không tự sửa dấu hoặc tên địa danh bằng từ điển/đáp án test. Không thay model hoặc tăng ngưỡng PAD để ép bộ ảnh này đạt. Lỗi PAD nhận nhầm ảnh thẻ là live trong báo cáo gốc vẫn là giới hạn của model trên ảnh tĩnh; dùng cùng thử thách camera và cần tập kiểm thử riêng. Chưa kiểm tra động tác người thật/video/deepfake trong lần nâng cấp này.

## Tự nhận diện mặt thẻ — phiên bản 0.2.1

Khi bấm Đọc thông tin hoặc Đọc nơi cư trú, máy chủ nhận diện mặt từ chữ OCR; kết quả không phụ thuộc ô bạn đã chọn. Mặt trước dùng kết hợp số căn cước, tên, ngày sinh và tiêu đề. Mặt sau dùng MRZ, nơi đăng ký khai sinh, ngày cấp, cơ quan cấp hoặc nhãn đặc trưng CCCD cũ. Không dùng riêng vị trí chip hay việc có địa chỉ để phân biệt mặt.

- Gửi mặt sau vào ô mặt trước: báo “Ảnh này là mặt sau…” và không điền thông tin.
- Gửi mặt trước vào ô mặt sau: báo “Ảnh này là mặt trước…” và không ghép địa chỉ.
- Ảnh ít chữ, selfie, hoặc có dấu hiệu cả hai mặt: báo chưa xác định được và yêu cầu chụp lại một mặt. Không đoán.
- Tự xoay ảnh vẫn chạy trước bước phân loại. Xuất JSON có `document_detection` cùng các dấu hiệu đã dùng. Đây là nhận diện bố cục theo quy tắc trên OCR, chưa xác thực CCCD thật/giả.

Test: chọn cố ý nhầm mặt ở từng ô rồi bấm đọc. Với ô mặt sau, đọc mặt trước đúng trước để mở nút đọc mặt sau. Chạy `test_side_real_models.py` để kiểm tra 20 lượt gửi từ 10 ảnh; 20/20 đã qua. `SIDE_TEST_RESULTS.json` lưu kết quả không chứa trường danh tính. Mặt sau CCCD cũ chưa có ảnh thực trong bộ gửi; chỉ kiểm tra quy tắc bằng dữ liệu chữ mô phỏng.

Giao diện ui-03 đã mở được trong trình duyệt tích hợp ở cổng 8879. Đã kiểm tra quét mặt trước, mặt sau và so khớp qua giao diện với model thật; xem `test-results/UI_03_REPORT.md`. Nếu đang mở giao diện cũ, nhấn Ctrl+F5 để tải lại CSS/JavaScript.

## So khớp mặt theo CCCD đã đọc — phiên bản 0.2.2

1. Trong **Đọc CCCD**, chọn mặt trước và bấm **Đọc thông tin**. Máy chủ lấy khuôn mặt từ chính ảnh mặt trước đã chỉnh hướng và tạo tham chiếu trong RAM. Nếu chưa tìm được đúng một khuôn mặt, thông tin OCR vẫn hiển thị nhưng chưa mở so khớp; cần chọn ảnh thẻ rõ hơn và đọc lại.
2. Mở **So khớp mặt**. Ảnh CCCD đã đọc xuất hiện ở ô khóa; không có ô tải ảnh tham chiếu riêng. Mặt sau chỉ bổ sung địa chỉ và không thay ảnh so khớp.
3. Chọn **selfie từ thiết bị**, hoặc bấm **Lấy selfie từ kiểm tra camera**, mở camera và làm thử thách. Khi phiên đạt cả động tác và ngưỡng PAD, bấm **Dùng selfie đã đạt thử thách để so khớp**. Hệ thống lấy khung hình đã được máy chủ chọn trong phiên, đưa về ô selfie.
4. Bấm **So khớp hai khuôn mặt**. Kết quả so selfie với khuôn mặt lưu từ lần đọc CCCD; không đọc lại ảnh tham chiếu gửi riêng.
5. Test đổi thẻ: sau khi so khớp thẻ A, chọn hoặc đọc lại mặt trước thẻ B. Ảnh tham chiếu, selfie và kết quả cũ bị xóa ngay. Kết quả OCR/so khớp/camera trả trễ của thẻ A không được điền vào B. Đọc thành công B rồi chọn selfie lại.

Tham chiếu có thời hạn 30 phút, chỉ giữ ảnh mặt cắt và đặc trưng trong RAM, tối đa 50 tham chiếu. Đổi thẻ, đóng trang hoặc khởi động lại máy chủ sẽ hủy tham chiếu tương ứng; khi hết hạn phải đọc lại mặt trước. Mã tham chiếu không xuất vào JSON tải về. API so khớp nhận `document_token` do /api/ocr mặt trước cấp và `selfie`; tải `reference` riêng không thể thay tham chiếu máy chủ.

Test riêng phần thay đổi: `test_face_reference.py`, `node test_ui.cjs`, và `test_locked_face_real_models.py` dùng `.venv\Scripts\python.exe` trong thư mục hiện tại. Kết quả model thật ghi trong `LOCKED_FACE_TEST_RESULTS.json`: 5 cặp (3 cùng người, 2 khác người), xóa tham chiếu, mặt sau không cấp tham chiếu và chặn ảnh tham chiếu tải riêng. Bộ logic/API có 38/38 bài qua. Handler camera và điều kiện lấy selfie đã được test; chưa thực hiện lại động tác người thật trước camera trong lần sửa này. Ảnh selfie tải từ thiết bị chỉ là so khớp mặt, không có kết quả thử thách camera.

## Thư mục sau khi dọn

Bản được giữ là `outputs/ekyc-prototype-v2`. Mở `DON_BAN_CU.cmd` để xóa các bản cũ và thư mục dựng thử theo các đường dẫn đã kiểm tra. Các báo cáo kiểm thử gốc được giữ tại `test-results/prototype-goc`; chúng là bằng chứng kiểm thử trước nâng cấp. Môi trường/model ở vị trí mới đã kiểm tra đạt. Lệnh xóa từ phiên trợ lý bị cơ chế phê duyệt tự động chặn; file DON_BAN_CU.cmd thực hiện việc dọn khi bạn chạy trực tiếp. Ảnh đầu vào trong Downloads/ảnh không bị thay đổi. Chi tiết dọn xem CLEANUP_REPORT.json.

