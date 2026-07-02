# Cấu hình gunicorn (prod). Đội <10 người → 1 worker gthread + ThreadPoolExecutor (jobs.py).
# 1 worker = mọi request cùng process → không cần polling chéo worker cho job nền.
bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = 1
threads = 8
timeout = 300
# KHÔNG preload_app: executor tạo lazy sau fork (tránh fork hỏng ThreadPoolExecutor).
preload_app = False
accesslog = "-"
errorlog = "-"
