# TableGeneration

通过浏览器渲染生成表格图像，代码修改自论文 [Rethinking Table Parsing using Graph Neural Networks](https://arxiv.org/pdf/1905.13391.pdf) [源代码](https://github.com/hassan-mahmood/TIES_DataGeneration) 。

修改后主要特性如下：

1. 支持更多参数可配置，如单元格类型，表格行列，合并单元格数量，
2. 支持彩色单元格
3. 内置四种类型表格，如下表所示

|类型|样例|
|---|---|
|简单表格|![](imgs/simple.jpg)|
|彩色表格|![](imgs/color.jpg)|
|清单表格|![](imgs/qd.jpg)|
|大单元格表格|![](imgs/big_cell.jpg)|

## 环境准备

安装python包

```bash
pip3 install -r requirements.txt
```

目前支持使用chrome浏览器和火狐浏览器。代码本身不限制只能在Linux或Mac上运行，Windows下也可以使用，但需要手动安装浏览器驱动并配置到环境变量中。使用方式分别如下

### chrome浏览器(Linux下推荐)

- 安装chrome浏览器和中文字体

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
apt-get update && sudo apt-get install libnss3
apt-get install xfonts-wqy
apt install ttf-wqy-zenhei
apt install fonts-wqy-microhei
# refresh fonts
fc-cache -fv
```

- 安装chrome浏览器驱动 chromedriver

首先在[官网](https://chromedriver.chromium.org/downloads)下载适合自己系统的驱动文件。然后执行下列命令

```shell
unzip chromedriver_linux64.zip
cp chromedriver /usr/local/share/
ln -s /usr/local/share/chromedriver /usr/local/bin/chromedriver
ln -s /usr/local/share/chromedriver /usr/bin/chromedriver
```

- 测试浏览器和chromedriver

使用如下命令测试chromedriver和chrome浏览器是否安装正确

```python
from selenium import webdriver

options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(chrome_options=options)
driver.get('https:www.baidu.com')
print(driver.title)
driver.close()
```

如果成功，会在终端看见如下输出

```bash
百度一下，你就知道
```

### Windows环境安装

Windows下推荐使用Chrome浏览器。安装步骤如下：

1. 安装Python依赖

```powershell
pip install -r requirements.txt
```

2. 安装Chrome浏览器

如果本机已经安装Chrome，可以跳过这一步。

3. 安装Chrome浏览器驱动 chromedriver

- 打开Chrome，在地址栏输入 `chrome://version/` 查看Chrome版本。
- 下载与Chrome主版本号匹配的 `chromedriver.exe`。
  - 新版本Chrome可从 [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/) 下载。
  - 旧版本Chrome可从 [ChromeDriver downloads](https://chromedriver.chromium.org/downloads) 下载。
- 解压后将 `chromedriver.exe` 放到一个固定目录，例如 `C:\WebDriver\bin\chromedriver.exe`。
- 将该目录加入系统环境变量 `Path`。

配置完成后，重新打开PowerShell，执行下面命令验证：

```powershell
chromedriver --version
```

如果能输出版本号，说明驱动已经可以被系统找到。

4. 安装中文字体

Windows通常已经包含中文字体。如果生成的图片中文字显示异常，可以安装常见中文字体，例如微软雅黑、宋体、黑体等，然后重新运行生成命令。

5. 测试浏览器和chromedriver

在项目目录下执行：

```powershell
@'
from selenium import webdriver

options = webdriver.ChromeOptions()
options.add_argument('--headless')
driver = webdriver.Chrome(chrome_options=options)
driver.get('https://www.baidu.com')
print(driver.title)
driver.close()
'@ | python
```

也可以新建一个临时Python文件运行：

```python
from selenium import webdriver

options = webdriver.ChromeOptions()
options.add_argument('--headless')
driver = webdriver.Chrome(chrome_options=options)
driver.get('https://www.baidu.com')
print(driver.title)
driver.close()
```

6. 生成表格

```powershell
python generate_data.py --output output/simple_table --num=1 --brower chrome
```

如果使用Firefox，也可以安装Firefox和 `geckodriver.exe`，并将 `geckodriver.exe` 所在目录加入 `Path`，然后运行：

```powershell
python generate_data.py --output output/simple_table --num=1 --brower firefox
```

### 常见问题

- `chromedriver executable needs to be in PATH`：说明 `chromedriver.exe` 没有加入环境变量 `Path`，或PowerShell没有重新打开。
- `session not created`：通常是Chrome和chromedriver版本不匹配，需要下载对应版本的驱动。
- 中文乱码或方框：安装中文字体后重新运行。
- 如果新版浏览器与 `selenium==3.8.1` 不兼容，可以优先更换匹配的浏览器驱动；仍无法解决时，再考虑升级Selenium并同步修改代码中的WebDriver调用方式。

### 火狐浏览器(Mac下推荐)

- 安装火狐浏览器和中文字体

```bash
apt-get -y install firefox
apt-get install xfonts-wqy
apt install ttf-wqy-zenhei
apt install fonts-wqy-microhei
# refresh fonts
fc-cache -fv
```

- 安装火狐浏览器驱动 geckodriver

首先在[官网](https://github.com/mozilla/geckodriver/releases/)下载适合自己系统的驱动文件。然后执行下列命令

```shell
tar -xf geckodriver-v0.31.0-linux64.tar.gz
cp geckodriver /usr/local/share/
ln -s /usr/local/share/geckodriver /usr/local/bin/geckodriver
ln -s /usr/local/share/geckodriver /usr/bin/geckodriver
```

- 测试浏览器和geckodriver

使用如下命令测试geckodriver和火狐是否安装正确

```python
from selenium import webdriver

options = webdriver.FirefoxOptions()
options.add_argument('--headless')
driver = webdriver.Firefox(firefox_options=options)
driver.get('https:www.baidu.com')
print(driver.title)
driver.close()
```

如果成功，会在终端看见如下输出

```bash
百度一下，你就知道
```

## 生成表格

### 生成表格

使用如下命令可生成表格，`ch_dict_path`和`en_dict_path`
不指定时，将会使用默认的中英文语料。最终生成的表格图片，表格html文件和PP-Structure格式标注文件会保存在`output`指定路径下。

```bash
# 简单表格
python3 generate_data.py --output output/simple_table --num=1
# 单元格坐标为单元格内文字坐标的表格
python3 generate_data.py --output output/simple_table --num=1 --cell_box_type='text'
# 彩色单元格表格
python3 generate_data.py --output output/color_simple_table --num=1 --color_prob=0.3
# 清单类表格
python3 generate_data.py --output output/qd_table --num=1 --min_row=10 --max_row=80 --min_col=4 --max_col=8 --min_txt_len=2 --max_txt_len=10 --max_span_row_count=3 --max_span_col_count=3 --max_span_value=20 --color_prob=0 --brower_width=1920 --brower_height=5000
# 大单元格表格
python3 generate_data.py --output output/big_cell_table --num=1 --min_row=6 --max_row=10 --min_col=4 --max_col=8 --min_txt_len=2 --max_txt_len=10 --max_span_row_count=3 --max_span_col_count=3 --max_span_value=10 --color_prob=0 --cell_max_width=100 --cell_max_height=100 --brower_width=1920 --brower_height=1920
```

### 校验数据

使用如下命令即可对生成的数据进行校验：

```bash
python3 vis_gt.py --image_dir path/to/imgs --gt_path path/to/gt.txt
```

这个命令会生成一个html页面，在html页面中会展示图片名、原图、表格的可视化和cell坐标。如下所示:

|类型| 样例                     |
|---|------------------------|
|cell坐标为单元格内文字坐标 | ![](imgs/text_box.jpg) |
|cell坐标为真实单元格坐标 | ![](imgs/cell_box.jpg) |

## 表格生成流程:

1. 随机生成表格行列
2. 随机生成表格合并单元格数量和合并的起始结束位置
3. 对于每一个单元格随机生成文本并组合成html字符串
4. 使用浏览器对html字符串进行渲染生成表格图片
5. 浏览器截图获取表格图片
6. 裁剪图片，只保留表格区域
7. 保存PP-Structure标注格式
