# BTTH_01-DS102_24521820
Bài tập thực hành 01 lớp DS102.R11.CNVN.1

# Thông tin người thực hiện
Họ và Tên: Phan Thị Thùy Trang

MSSV: 24521820

Gmail: 24521820@gm.uit.edu.vn

# Nội dung bài thực hành
## 1. Tìm hiểu và xây dựng thuật toán Newton-Raphson tìm điểm cực trị của một hàm thực vector sử dụng NumPy
Bài làm được lưu trong file `newton_raphson.py`, mô tả:
- Làm bài cơ bản, thực hiện tính toán sẵn trên 2 hàm
- Đánh giá: thiếu hướng làm tổng quát hóa (em chưa hiểu nguyên cái hệ vector làm kiểu gì :))) nên e chỉ tự làm lại với 1 ví dụ khác với bài sửa trên lớp)

## 2. Thực hiện thu thập dữ liệu từ một trang web bất kỳ. Lưu dữ liệu dưới dạng các file TSV, CSV, hoặc JSON
Bài làm được chia làm 2 file: 
1. Cào dữ liệu từ API: `api_crawler_unsplash.py`
2. Phân tích cơ bản bộ dữ liệu sau khi cào (chưa tiền xử lý): `EDA.ipynb`
3. Dữ liệu metadata của ảnh: `unsplash_metadata.csv`
- Thực hiện cào dữ liệu hình ảnh trên Unsplash
- Đánh giá: quy mô bộ dữ liệu chưa lớn (định hướng cào thêm để đạt tới bộ dữ liệu 10000 ảnh), chủ đề của ảnh còn giao thoa (chọn dựa trên cảm tính người làm), EDA cơ bản chỉ đánh giá 3 yếu tố: khuyết dữ liệu, phân phối của các cột: 'likes', 'width', 'height' để đánh giá chất lượng ảnh và mức độ ảnh hưởng của ảnh (các yếu tố khác sẽ được EDA khi có một bài toán cụ thể để hướng tới)
