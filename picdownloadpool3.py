import sys
import os
import time
import random
import shutil
import requests
import re
import queue
from multiprocessing import Pool
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QProgressBar, QLineEdit, 
                            QLabel, QTextEdit, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from pathlib import Path

class ListfilmWorker(QThread):
	#此线程用来遍历目录下所有的影片，避免UI窗口假死无相应
	progress = pyqtSignal(int) #定义信号，发送所有影片的数量
	finished = pyqtSignal(list)  # 定义信号，用于在工作线程和主窗口之间传递信息
	thread_started = pyqtSignal()  # 定义线程开始时发送的信号
	def __init__(self, directory_path):
		super().__init__()
		self.directory_path = directory_path
	def run(self):
		self.thread_started.emit()  # 发送线程启动信号
		mp4_files = []
		#self.log_display.clear
		#self.log_display.append(f"[{time.ctime()}] 遍历文件中，请等待...")
		for root, dirs, files in os.walk(self.directory_path):
			for file in files:
				if file.endswith('.mp4') or file.endswith('.avi'):
					file_path = os.path.join(root, file)
					file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
					if file_size_mb > 100:#大于100MB
						 mp4_files.append(file_path)
		# 发送完成信号，传递找到的所有 .mp4 文件列表
		#print(mp4_files)
		#self.log_display.clear
		#self.log_display.append(f"[{time.ctime()}] 遍历文件结束！")
		self.progress.emit(len(mp4_files))
		self.finished.emit(mp4_files)



class DownloadWorker(QThread):
    progress = pyqtSignal(int,int)#发送已经下载的图片数量
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, start_num, end_num, output_dir, car_prefix="waaa", filmname=""):
        super().__init__()
        self.base_url = "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video"
        self.output_dir = output_dir
        self.start_num = start_num
        self.filmname = filmname
        #print('self.filmname',self.filmname)
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
            if response.status_code == 200 and len(response.content) > 10240:
                print(url,save_path)
                Path(os.path.dirname(save_path)).mkdir(exist_ok=True)
                with open(save_path + '.mp4', 'wb') as f:#修改Jpg文件为mp4，让emby支持剧照
                    f.write(response.content)
                    postername = '.'.join(self.filmname.split('.')[:-1]) + '-poster.jpg'
                    #print('postername=',postername)
                    backsave_path = os.path.dirname(os.path.dirname(save_path))#上上以及目录
                    dest_jpg_poster = os.path.join(backsave_path,postername)
                    if 'ps.jpg' in save_path :#下载的图片包含高清poster的封面图
                        poster_jpg = os.path.join(backsave_path,'poster.jpg')#poster.jpg原来存在
                        movecheck = os.path.exists(poster_jpg) and not os.path.exists(dest_jpg_poster) and os.path.getsize(poster_jpg) > os.path.getsize(save_path + '.mp4')                            
                        if (not os.path.exists(dest_jpg_poster) or os.path.getsize(save_path + '.mp4') > os.path.getsize(dest_jpg_poster)) and not movecheck:
                            shutil.copy2(save_path + '.mp4', dest_jpg_poster)
                return True, 200
            return False, response.status_code
        except requests.RequestException as e:
            return False, 503

    def stop(self):
        self.is_running = False

    def run(self):
        #total_files = (self.end_num - self.start_num + 1) * len(self.download_tasks)
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
                
                #processed += 1
                filename = f"{car_id}{task['suffix']}.jpg"
                file_url = f"{self.base_url}/{car_id}/{filename}"
                save_path = os.path.join(car_dir, filename)

                self.progress.emit(1,len(self.download_tasks))

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
        self.tasks_queue = queue.Queue()
        self.total_files = 0
        self.current = 0
        self.runningworkers = []#正在运行的workers
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
        
        input_layout.addWidget(QLabel("默认线程数:"))
        self.thread_num = QLineEdit("10")
        self.thread_num.setMaximumWidth(80)
        input_layout.addWidget(self.thread_num)
        
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

    def on_files_found(self, filespath):
        #print(filespath)
        thread_num = int(self.thread_num.text())
        num_sub_queues = thread_num  # 设置子队列的数量
        self.runningworkers = []
        def distribute_tasks(tasks_queue, num_sub_queues):
            sub_queues = [queue.Queue() for _ in range(num_sub_queues)]
            # 将 tasks_queue 中的任务均匀分配到子队列中
            while not tasks_queue.empty():
                task = tasks_queue.get()
                index = hash(task) % num_sub_queues  # 基于任务的哈希值选择子队列索引
                sub_queues[index].put(task)
            return sub_queues
        def process_next_task(tasks_queue):
            if tasks_queue.empty():
                self.log_display.append(f"[{time.ctime()}] 一个线程完成下载任务！")
                return
            current_thread = tasks_queue.get()
            if tasks_queue.qsize() == 0:
                self.log_display.append(f"[{time.ctime()}] {current_thread.filmname}最后一个下载任务进行中，马上结束此线程！")
            # 在这里，你可以选择等待工作完成或者设置为非阻塞处理
            # 如果你需要确保所有任务按顺序完成（即一个开始后等待它结束再启动下一个），可以使用类似以下代码：
            current_thread.finished.connect(lambda: process_next_task(tasks_queue))
            current_thread.finished.connect(current_thread.quit)  # 请求线程退出
            current_thread.finished.connect(current_thread.wait)  # 等待线程退出
            current_thread.finished.connect(current_thread.deleteLater)
            #total_files = (current_thread.end_num - current_thread.start_num + 1) * len(current_thread.download_tasks)
            self.progress_bar.setMaximum(self.total_files)
            self.progress_bar.setValue(0)
            current_thread.progress.connect(self.update_progress)
            current_thread.log.connect(self.update_log)
            current_thread.finished.connect(self.download_finished)
            self.runningworkers.append(current_thread)# 将线程添加到列表中以便管理
            current_thread.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            print('开始一个DownloadWorker，下载一个番号对应的多个jpg的url地址')
            #current_thread.start()  # 启动当前从队列中取出的线程
            # 开始处理队列中的第一个任务
        for file_path in filespath:
            bn = os.path.basename(os.path.dirname(file_path))
            filenamewithoutpath = os.path.basename(file_path)
            if re.search(r'[A-Za-z]+', bn) is None:
                continue
            car_prefix = re.search(r'[A-Za-z]+', bn).group(0)
            match = re.search(r'\d+', bn)
            start_num = int(match.group(0))
            if re.search(r'-(\d+)', bn):
                start_num = int(re.search(r'-(\d+)', bn).group(1))
                end_num = start_num
                output_dir = os.path.dirname(file_path)
                #print(start_num,end_num,output_dir,car_prefix, bn)
                self.worker = DownloadWorker(start_num, end_num, output_dir, car_prefix, filenamewithoutpath)
                self.tasks_queue.put(self.worker)


        sub_queues = distribute_tasks(self.tasks_queue,num_sub_queues)

        for i in range(num_sub_queues):
            if not sub_queues[i].empty():
                print(f"分配 sub-queue {i},开始运行sub-queue里的worker，分配的sub-queue同时运行，做到多线程运行worker")
                process_next_task(sub_queues[i])#多线程开始运行每个sub queue



    def start_download(self):#鼠标点击下载就开始这个函数
        try:
            start_num = int(self.start_input.text())
            end_num = int(self.end_input.text())
            thread_num = int(self.thread_num.text())
            if thread_num > 50 or thread_num < 1:
                raise ValueError("输入的线程数超过50或者低于1")
            output_dir = self.dir_input.text()
            car_prefix = self.prefix_input.currentText().strip()
            directory = output_dir
            if not (os.path.exists(directory) and (os.path.isfile(directory) or os.path.isdir(directory))):
                raise ValueError("输入的目录地址不对,请检查目录有效性")
            if not car_prefix:
                raise ValueError("番号前缀不能为空")
            self.tasks_queue = queue.Queue()
            #new_subdirectory_name = 'behind the scenes'
            filmworker = ListfilmWorker(directory)
            filmworker.thread_started.connect(self.listfilmstart)
            filmworker.progress.connect(self.calc_total_files)
            filmworker.finished.connect(self.on_files_found)
            filmworker.finished.connect(filmworker.quit)  # 请求线程退出
            filmworker.finished.connect(filmworker.wait)  # 等待线程退出
            filmworker.finished.connect(filmworker.deleteLater)
            filmworker.finished.connect(self.listfilmend)
            filmworker.start()


            # for root, dirs, files in os.walk(directory):
                # for file in files:
                    # if file.endswith('.mp4') or file.endswith('.avi'):
                        # file_path = os.path.join(root, file)
                        # file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        # bn = os.path.basename(os.path.dirname(file_path))
                        # if file_size_mb > 100:#大于100MB
                            # #car_prefix  = bn.split('-')[0]
                            # if re.search(r'[A-Za-z]+', bn) is None:
                                # continue
                            # car_prefix = re.search(r'[A-Za-z]+', bn).group(0)
                            # match = re.search(r'\d+', bn)
                            # start_num = int(match.group(0))
                            # if re.search(r'-(\d+)', bn):
                                # start_num = int(re.search(r'-(\d+)', bn).group(1))
                            # end_num = start_num
                            # output_dir = root
                            # self.worker = DownloadWorker(start_num, end_num, output_dir, car_prefix, file)
                            # tasks_queue.put(self.worker)
                            # self.log_display.clear()
                            # self.log_display.append(f"[{time.ctime()}] 遍历文件中，请等待...
        except ValueError as e:
            self.log_display.append(f"错误: {str(e)}")



    def calc_total_files(self,total_files):
        self.total_files = total_files

    def stop_download(self):
        # 将队列的所有元素放到一个临时列表中
        #temp_list = []
        #while not self.tasks_queue.empty():
        #    worker = self.tasks_queue.get()#回收还在queue里没有运行的worker
        #    del worker
        for runningworker in self.runningworkers:
            if runningworker.isFinished():
                continue
            if hasattr(self, 'worker') and runningworker.isRunning():
                runningworker.stop()#停止已经正在运行的workers
        self.stop_button.setEnabled(False)
        self.current = 0
        self.progress_bar.setValue(self.current)
        self.total_files = 0
        #self.progress_bar.setMaximum(self.total_files)

    def update_progress(self,increment=1,lentask=1):
        self.current += increment
        self.progress_bar.setValue(self.current)
        total_pics = self.total_files * lentask
        self.progress_bar.setMaximum(total_pics)
        filename = f"{self.worker.generate_car_id(self.worker.start_num + (self.current // len(self.worker.download_tasks)))}{self.worker.download_tasks[self.current % len(self.worker.download_tasks)]['suffix']}.jpg"
        self.setWindowTitle(f"DMM图片下载器 - {self.current}/{total_pics} ({filename})")

    def update_log(self, message):
        self.log_display.append(message)

    def listfilmstart(self):
        self.log_display.clear
        self.log_display.append(f"[{time.ctime()}] 遍历文件中，请等待...")

    def listfilmend(self):
        self.log_display.clear
        self.log_display.append(f"[{time.ctime()}] 遍历文件结束！")

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
