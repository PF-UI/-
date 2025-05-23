
# ICT招聘数据分析项目
## 一、项目概述
ICT招聘数据分析项目旨在通过对ICT领域招聘数据的收集、存储、分析及可视化，为求职者和企业提供洞见。项目涵盖数据爬取、清洗、存储、多维度分析（技能词云、岗位分布热力图、薪资分布）及交互式GUI界面，支持用户查询岗位信息并生成统计图表。

## 二、项目结构
```
ICT招聘数据分析项目
├─ bin/                # 核心代码模块
│  ├─ ConfigLoader.py   # 配置加载器
│  ├─ DataAnalyzer.py   # 数据分析模块
│  ├─ DataAnalyzerApp.py# GUI界面模块
│  ├─ DataStorage.py    # 数据存储模块
│  └─ JobDataCollector.py# 数据采集模块
├─ config/             # 配置文件
│  └─ config.yaml       # 系统配置（数据库、日志、文件路径等）
├─ data/               # 原始数据存储
│  ├─ 2022年ICT相关专业招聘数据.csv
│  ├─ 2024ICT数据.csv
│  └─ jobs_data.jsonl   # 爬取的实时招聘数据
├─ logs/               # 日志文件
├─ result/             # 分析结果存储
│  ├─ heatmap/         # 热力图
│  ├─ salary/          # 薪资分布图
│  └─ wordcloud/       # 词云图
├─ html/               # 可视化报告（HTML格式）
├─ scripts/            # 脚本文件（可选）
├─ main.py             # 主程序入口
└─ README.md           # 项目说明文档
```

## 三、核心功能
### 1. 数据采集
- **模块**：`JobDataCollector.py`
- **功能**：通过多线程爬取前程无忧等招聘平台的ICT职位数据（如ICT工程师、5G工程师等），支持去重和断点续传。
- **参数**：
  - `job_titles`：目标职位列表（如["ICT工程师", "5G工程师"]）。
  - `city_code`：城市代码（默认736，对应北京）。
  - `max_workers`：最大线程数（默认5）。

### 2. 数据存储
- **模块**：`DataStorage.py`
- **功能**：清洗不同格式的原始数据（CSV/Excel/JSON），并存储到MySQL数据库。支持分批次写入和错误重试。
- **支持年份**：2022-2025年（不同年份数据需按指定格式预处理）。

### 3. 数据分析与可视化
- **模块**：`DataAnalyzer.py`
- **功能**：
  - **技能词云**：从职位要求中提取高频技能词，生成词云图。
  - **岗位热力图**：按省份统计岗位分布，生成交互式热力图。
  - **薪资分布**：解析薪资范围，生成直方图和扇形图，展示薪资区间占比。
- **输出**：图片文件（PNG）和HTML报告。

### 4. 交互式GUI界面
- **模块**：`DataAnalyzerApp.py`
- **功能**：
  - **岗位查询**：支持按职位名称、薪资范围、工作地点筛选岗位。
  - **可视化展示**：动态显示各年份的词云图、热力图和薪资分布图。
  - **数据导出**：将查询结果导出为CSV文件。

## 四、环境要求
### 1. 依赖库
```python
pymysql         # 数据库连接
requests        # 数据爬取
pandas          # 数据处理
matplotlib      # 图表绘制
jieba           # 中文分词
wordcloud       # 词云生成
pyecharts       # 交互式可视化
scipy           # 统计分析
tkinter         # GUI界面
```

### 2. 工具版本建议
- Python 3.8+
- MySQL 5.7+（需创建数据库，配置见`config/config.yaml`）
- 浏览器（推荐Chrome，用于查看HTML报告）

## 五、快速启动
### 1. 配置文件设置
- **路径**：`config/config.yaml`
- **关键配置项**：
  ```yaml
  database:       # 数据库配置
    host: localhost
    user: root
    password: your_password
    database: recruitment
  logging:        # 日志配置
    log_dir: logs
    file_prefix: analysis
  data_files:     # 各年份数据文件路径
    2022: data/2022年ICT相关专业招聘数据.csv
    2023: ["data/2023年数据1.xlsx", "data/2023年数据2.xlsx"]
    2024: data/2024ICT数据.csv
    2025: data/jobs_data.jsonl
  images:         # 图表保存路径
    wordcloud: result/wordcloud/
    heatmap: result/heatmap/
    salary: result/salary/
  ```

### 2. 运行主程序
```bash
# 克隆项目
git clone https://github.com/your-username/ict-recruitment-analysis.git
cd ict-recruitment-analysis

# 安装依赖
pip install -r requirements.txt

# 运行主程序（可通过修改main.py中的开关控制流程）
python main.py
```

### 3. 界面操作
- 启动后自动打开GUI界面，包含“岗位信息查询统计”和“数据可视化”两个选项卡。
- 在“岗位信息查询统计”中输入条件，点击“查询”获取岗位列表，支持薪资统计和数据导出。
- 在“数据可视化”中选择图表类型（词云图/热力图/薪资分布图）和年份，查看结果。

## 六、维护与扩展
### 1. 数据爬取扩展
- 修改`JobDataCollector.py`中的`job_titles`和`city_code`，新增目标职位或城市。
- 调整`max_workers`参数优化爬取速度（建议不超过10，避免IP封禁）。

### 2. 数据分析扩展
- 在`DataAnalyzer.py`中新增分析维度（如学历要求、经验要求分布）。
- 修改可视化参数（如颜色、字体、图表尺寸），优化展示效果。

### 3. 配置扩展
- 在`config.yaml`中新增数据文件路径或日志格式，适应不同数据源。

## 七、注意事项
1. 数据爬取需遵守招聘平台的robots协议，避免频繁请求导致IP封禁。
2. 处理大规模数据时，建议调整`DataStorage.py`中的`batch_size`（默认1000条/批），避免内存溢出。
3. GUI界面首次加载图表可能较慢，需等待数据处理完成。

## 八、联系方式
- **邮箱**：your-email@example.com
- **问题反馈**：在项目仓库提交Issue。
