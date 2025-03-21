# EMBY_AV_Fanartpicture
## 下载emby的AV高清剧照<br>
根据指定的目录，遍历目录下所有的MP4文件或者AVI文件(文件大小大于100MB),影片需要在符合命名规则目录下<br>
比如 adn-008_强上你.mp4文件，需要在目录adn-008下，因为番号根据目录来获取，不是根据影片名来获取<br>
所以每个影片需要保存在对应的目录名下<br>
在影片所在目录下建立behind the scenes目录<br>
根据影片的AV番号,去网上下载高清剧照,保存在behind the scenes目录下,并且所有下载的jpg文件自动加上扩展名.mp4<br>
然后扫描emby影片,就能在页面上显示剧照了<br>
如果下载的剧照包含poster.jpg封面，自动复制高清剧照到硬盘所在目录，命名为影片名-poster.jpg<br>
需要pip install PyQt5,安装PyQt5，需要安装环境微软vs_BuildTools，下载地址报错的时候会显示,安装环境的时候选择第一个栏目，然后继续.安装完成后再运行pip install PyQt5<br>
picdownload.py文件用所有线程同时下载每个影片的图片，picdownloadonebyonethread.py用一个线程依次下载每个电影的图片。注意picdownload.py同时打开很多个链接<br>
picdownloadpool2.py可以指定线程数从1-50<br>
picdownloadpool3.py多线程改进版，修正了一些错误
