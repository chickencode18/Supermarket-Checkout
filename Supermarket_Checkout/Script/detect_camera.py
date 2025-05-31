from ultralytics import YOLO
import cv2
import pyodbc
from flask import Flask, render_template
from threading import Thread

app = Flask(__name__)

total_price = 0
total_quantity = 0
products_detected = {}  # Lưu dưới dạng dict: {product_name: {'price': ..., 'quantity': ...}}

conn = pyodbc.connect(r'DRIVER={ODBC Driver 17 for SQL Server};'
                      r'SERVER=LAPTOP-45F3Q35V\SQLEXPRESS;'
                      r'DATABASE=Products;'
                      r'Trusted_Connection=yes;')
cursor = conn.cursor()

model = YOLO(r"D:/code/Computer_vision/runs/detect/train/weights/best.pt")

@app.route("/checkout")
def checkout():

    product_list = [{'name': name, 'price': info['price'], 'quantity': info['quantity']}
                    for name, info in products_detected.items()]
    return render_template("checkout.html",
                           products=product_list,
                           total_price=total_price,
                           total_quantity=total_quantity)

def run_flask():
    app.run(debug=True, use_reloader=False)

def run_camera():
    global total_price, total_quantity, products_detected

    cap = cv2.VideoCapture(0)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, conf=0.4)

        # Đếm sản phẩm trong frame hiện tại
        current_frame_counts = {}

        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = box.conf[0].item()
                cls = int(box.cls[0].item())

                product_name = model.names[cls]
                label = f"{product_name} {conf:.2f}"

                current_frame_counts[product_name] = current_frame_counts.get(product_name, 0) + 1

                cursor.execute('SELECT * FROM SANPHAM WHERE Names = ?', product_name)
                product = cursor.fetchone()

                if product:
                    if product_name not in products_detected:
                        products_detected[product_name] = {
                            'price': product.Price,
                            'quantity': 0
                        }

                    # So sánh với quantity cũ
                    prev_qty = products_detected[product_name]['quantity']
                    curr_qty = current_frame_counts[product_name]

                    if curr_qty > prev_qty:
                        delta = curr_qty - prev_qty
                        products_detected[product_name]['quantity'] = curr_qty
                        total_price += delta * product.Price
                        total_quantity += delta

                    # Hiển thị bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Hiển thị thông tin
        cv2.putText(frame, f"Tong so luong: {total_quantity}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Tong tien: {total_price:.2f} VND", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("YOLOv8 Detection", frame)

        if cv2.waitKey(1) & 0xFF == 27 :
            break

    cap.release()
    cv2.destroyAllWindows()
    cursor.close()
    conn.close()
    print("Camera stopped. Mở trình duyệt: http://127.0.0.1:5000/checkout")

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    run_camera()