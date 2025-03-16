import sys
import os
import time
import random
import shutil
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QProgressBar, QLineEdit, 
                            QLabel, QTextEdit, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path

class DownloadWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, start_num, end_num, output_dir, car_prefix="waaa", filmname=""):
        super().__init__()
        self.base_url = "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video"
        self.output_dir = output_dir
        self.start_num = start_num
        self.filmname = filmname
        self.end_num = end_num
        self.retry_count = 1
        self.base_delay = 1
        self.car_prefix = car_prefix
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
        ]
        self.download_tasks = [
            {"suffix": "pl", "type": "cover"},
            {"suffix": "ps", "type": "cover"}
        ] + [{"suffix": f"jp-{i}", "type": "preview"} for i in range(1, 16)]
        self.is_running = True
        self.initialize_environment()

    def initialize_environment(self):
        try:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            self.log.emit(f"[{time.ctime()}] Directory created: {self.output_dir}")
            self.log_path = os.path.join(self.output_dir, "download.log")
        except Exception as e:
            self.log.emit(f"[{time.ctime()}] Initialization failed: {str(e)}")
            raise

    def generate_car_id(self, number):
        try:
            return f"{self.car_prefix}{number:05d}"
        except Exception as e:
            self.log.emit(f"[{time.ctime()}] Number conversion error: {str(e)}")
            raise

    def download_file(self, url, save_path):
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Referer": "https://www.dmm.co.jp/",
            "DNT": "1"
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
            print(url,save_path)
            if response.status_code == 200 and len(response.content) > 10240:

                Path(os.path.dirname(save_path)).mkdir(exist_ok=True)
                with open(save_path + '.mp4', 'wb') as f:#修改Jpg文件为mp4，让emby支持剧照
                    f.write(response.content)
                    postername = self.filmname.split('.')[0] + '-poster.jpg'
                    backsave_path = os.path.dirname(os.path.dirname(save_path))#上上以及目录
                    dest_jpg_poster = os.path.join(backsave_path,postername)
                    if 'ps.jpg' in save_path :#下载的图片包含高清poster的封面图
                        if not os.path.exists(dest_jpg_poster) or os.path.getsize(save_path + '.mp4') > os.path.getsize(dest_jpg_poster):
                            shutil.copy2(save_path + '.mp4', dest_jpg_poster)
                return True, 200
            return False, response.status_code
        except requests.RequestException as e:
            return False, 503

    def stop(self):
        self.is_running = False

    def run(self):
        total_files = (self.end_num - self.start_num + 1) * len(self.download_tasks)
        processed = 0

        for num in range(self.start_num, self.end_num + 1):
            if not self.is_running:
                self.log.emit(f"[{time.ctime()}] Download stopped by user")
                break

            car_id = self.generate_car_id(num)
            #car_dir = os.path.join(self.output_dir, car_id)
            car_dir = os.path.join(self.output_dir,'behind the scenes')
            #Path(car_dir).mkdir(exist_ok=True)

            thinkfaildtimes = 0
            for task in self.download_tasks:
                if not self.is_running:
                    break
                if thinkfaildtimes > 3:
                    break #如果下载次数大于3次，就认为这个番号不能下载图片了
                
                processed += 1
                filename = f"{car_id}{task['suffix']}.jpg"
                file_url = f"{self.base_url}/{car_id}/{filename}"
                save_path = os.path.join(car_dir, filename)

                self.progress.emit(processed, total_files)

                if os.path.exists(save_path):
                    self.log.emit(f"[{time.ctime()}] File exists: {filename}.mp4")
                    continue

                success, code = self.download_file(file_url, save_path)
                if success:
                    self.log.emit(f"[{time.ctime()}] Success: {filename}")
                    time.sleep(random.uniform(2, 5))
                elif code == 404:
                    thinkfaildtimes += 1
                    self.log.emit(f"[{time.ctime()}] Not found: {filename}")
                else:
                    self.log.emit(f"[{time.ctime()}] Failed: {filename} (Code: {code})")

        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DMM Image Downloader")
        self.setGeometry(100, 100, 600, 400)

        # Main widget and layout
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # Input fields (top row)
        input_layout = QHBoxLayout()
        readme1 = QHBoxLayout()
        readme1.addWidget(QLabel("根据你下面输入的地址，分析mp4或avi文件所在的目录的番号,在影片文件所在的目录下,建立behind the scenes目录"))
        readme2 = QHBoxLayout()
        readme2.addWidget(QLabel("所有下载的图片文件保存在behind the scenes，并且后面加上后缀.mp4。这样做的目的是让emby能显示剧照，需要手动扫描媒体库文件"))
        layout.addLayout(input_layout)
        layout.addLayout(readme1)
        layout.addLayout(readme2)
        input_layout.addWidget(QLabel("番号前缀:"))
        self.prefix_input = QComboBox()
        self.prefix_input.addItems(["不用管这个"])
        self.prefix_input.setEditable(True)
        self.prefix_input.setMinimumWidth(150)
        input_layout.addWidget(self.prefix_input)

        input_layout.addWidget(QLabel("起始编号:"))
        self.start_input = QLineEdit("1")
        self.start_input.setMaximumWidth(80)
        input_layout.addWidget(self.start_input)
        
        input_layout.addWidget(QLabel("结束编号:"))
        self.end_input = QLineEdit("1")
        self.end_input.setMaximumWidth(80)
        input_layout.addWidget(self.end_input)

        # Output directory (separate row below)
        output_layout = QHBoxLayout()
        layout.addLayout(output_layout)
        
        output_layout.addWidget(QLabel("选择要根据mp4或者avi文件下载对应图片的目录,《注意》会遍历所有子目录:"))
        #self.dir_input = QLineEdit(os.path.join(os.getcwd(), "dmm_images"))
        self.dir_input = QLineEdit('填写目录地址到这里')
        self.dir_input.setMinimumWidth(400)
        self.dir_input.setToolTip(self.dir_input.text())
        self.dir_input.textChanged.connect(lambda: self.dir_input.setToolTip(self.dir_input.text()))
        output_layout.addWidget(self.dir_input)

        # Button layout
        button_layout = QHBoxLayout()
        layout.addLayout(button_layout)
        
        self.start_button = QPushButton("开始下载")
        self.start_button.clicked.connect(self.start_download)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("停止下载")
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(1000)
        self.progress_bar.setFormat("%p% (文件: %v/%m)")
        layout.addWidget(self.progress_bar)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

        # Apply QSS (Plum Blossom Theme)
        self.setStyleSheet("""
            QWidget {
                background-color: #FFF0F5;
                font-family: Arial;
            }
            QPushButton {
                background-color: #FFB6C1;
                color: #4B0082;
                border: 1px solid #DDA0DD;
                padding: 5px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #FF69B4;
            }
            QPushButton:disabled {
                background-color: #D3D3D3;
                color: #808080;
            }
            QLineEdit, QComboBox {
                background-color: white;
                border: 1px solid #DDA0DD;
                padding: 3px;
                border-radius: 3px;
            }
            QProgressBar {
                border: 1px solid #DDA0DD;
                border-radius: 5px;
                text-align: center;
                background-color: white;
            }
            QProgressBar::chunk {
                background-color: #FFB6C1;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #DDA0DD;
                border-radius: 3px;
            }
            QLabel {
                color: #4B0082;
            }
        """)

    def start_download(self):
        try:
            start_num = int(self.start_input.text())
            end_num = int(self.end_input.text())
            output_dir = self.dir_input.text()
            car_prefix = self.prefix_input.currentText().strip()
            directory = output_dir
            if not (os.path.exists(directory) and (os.path.isfile(directory) or os.path.isdir(directory))):
                raise ValueError("输入的目录地址不对,请检查目录有效性")
            if not car_prefix:
                raise ValueError("番号前缀不能为空")

            #new_subdirectory_name = 'behind the scenes'
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.mp4') or file.endswith('.avi'):
                        file_path = os.path.join(root, file)
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        bn = os.path.basename(os.path.dirname(file_path))
                        if file_size_mb > 100:#大于100MB
                            car_prefix = bn.split('-')[0]
                            start_num = int(bn.split('-')[1])
                            end_num = start_num
                            output_dir = root
                            
                            self.worker = DownloadWorker(start_num, end_num, output_dir, car_prefix, file)
                            total_files = (end_num - start_num + 1) * len(self.worker.download_tasks)
                            self.progress_bar.setMaximum(total_files)
                            self.progress_bar.setValue(0)

                            self.worker.progress.connect(self.update_progress)
                            self.worker.log.connect(self.update_log)
                            self.worker.finished.connect(self.download_finished)
                            self.worker.start()

                            self.start_button.setEnabled(False)
                            self.stop_button.setEnabled(True)
        except ValueError as e:
            self.log_display.append(f"错误: {str(e)}")

    def stop_download(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.stop_button.setEnabled(False)

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)
        filename = f"{self.worker.generate_car_id(self.worker.start_num + (current // len(self.worker.download_tasks)))}{self.worker.download_tasks[current % len(self.worker.download_tasks)]['suffix']}.jpg"
        self.setWindowTitle(f"DMM图片下载器 - {current}/{total} ({filename})")

    def update_log(self, message):
        self.log_display.append(message)

    def download_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.log_display.append(f"[{time.ctime()}] 下载完成！")
        self.setWindowTitle("DMM图片下载器")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
