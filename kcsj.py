import random
import threading
from queue import Queue
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import requests
import time
import pandas as pd
from pymysql import Error
import json
from tqdm import tqdm
import pymysql
import logging
import matplotlib.pyplot as plt
import re
import math
import numpy as np
from datetime import datetime
import jieba
from pyecharts.options import TitleOpts, VisualMapOpts
from wordcloud import WordCloud
from collections import Counter
from pyecharts import options as opts
from pyecharts.charts import Geo, Map
from pyecharts.globals import ChartType
from scipy.stats import gaussian_kde

# 数据获取模块
class JobDataCollector:
    def __init__(self, output_file='jobs_data.jsonl', city_code='736', max_workers=5):
        """
        初始化数据采集器

        :param output_file: 输出文件名
        :param city_code: 城市代码(默认736)
        :param max_workers: 最大线程数
        """
        self.base_json_data = {
            'S_SOU_WORK_CITY': city_code,
            'order': 4,
            'pageSize': 20,
            'pageIndex': 1,
            'eventScenario': 'pcSearchedSouSearch',
            'anonymous': 1,
        }
        self.output_file = output_file
        self.existing_jobs = set()  # 用于去重的集合
        self.max_workers = max_workers
        self.lock = threading.Lock()  # 线程锁
        self.job_queue = Queue()  # 职位队列
        self.page_queue = Queue()  # 页码队列
        self._init_output_file()
        self.stats = {
            'total_jobs': 0,
            'success_jobs': 0,
            'failed_jobs': 0,
            'start_time': time.time()
        }

    def _init_output_file(self):
        """初始化输出文件"""
        try:
            # 尝试读取已有数据建立去重集合
            with open(self.output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    job = json.loads(line.strip())
                    job_key = (job["职位名称"], job["公司名称"])
                    self.existing_jobs.add(job_key)
        except FileNotFoundError:
            # 文件不存在则创建
            with open(self.output_file, 'w', encoding='utf-8') as f:
                pass

    def _extract_job_info(self, job_item, title):
        """提取职位信息并添加搜索职位字段"""
        job_info = {
            "职位名称": job_item.get("name", ""),
            "公司名称": job_item.get("companyName", ""),
            "薪资范围": job_item.get("salary60") or job_item.get("salaryReal", ""),
            "工作地点": f'{job_item.get("workCity", "")} {job_item.get("cityDistrict", "")} {job_item.get("streetName", "")}'.strip(),
            "经验要求": job_item.get("workingExp", "经验不限"),
            "学历要求": job_item.get("education", "不限"),
            "招聘人数": job_item.get("recruitNumber", 0),
            "职位类型": job_item.get("subJobTypeLevelName", ""),
            "公司性质": job_item.get("propertyName", ""),
            "公司规模": job_item.get("companySize", ""),
            "行业领域": job_item.get("industryName", ""),
            "福利待遇": job_item.get("welfareTagList", []) or
                        [tag["itemValue"] for tag in job_item.get("jobKeyword", {}).get("keywords", [])
                         if tag.get("itemValue")],
            "职位要求": {
                "技能标签": [skill["value"] for skill in job_item.get("skillLabel", [])],
                "职位描述": job_item.get("jobSummary", "").replace("\n", " ").strip(),
                "专业技能": [tag["name"] for tag in job_item.get("jobSkillTags", [])]
            },
            "其他信息": {
                "发布时间": job_item.get("publishTime", ""),
                "职位链接": job_item.get("positionUrl", ""),
                "公司链接": job_item.get("companyUrl", ""),
                "地铁线路": [f'{subway["lineName"]}-{subway["stationName"]}({subway["distance"]}米)'
                             for subway in job_item.get("subways", [])],
                "企业标签": job_item.get("industryCompanyTags", [])
            },
            "搜索职位": title
        }
        return job_info

    def _save_unique_jobs(self, job_infos):
        """线程安全的存储去重后的职位数据"""
        with self.lock:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                for job in job_infos:
                    job_key = (job["职位名称"], job["公司名称"])
                    if job_key not in self.existing_jobs:
                        self.existing_jobs.add(job_key)
                        f.write(json.dumps(job, ensure_ascii=False) + '\n')
                        self.stats['success_jobs'] += 1

    def _fetch_page(self, title, page):
        """获取单页数据"""
        json_data = self.base_json_data.copy()
        json_data['S_SOU_FULL_INDEX'] = title
        json_data['pageIndex'] = page

        try:
            response = requests.post(
                'https://fe-api.zhaopin.com/c/i/search/positions',
                json=json_data,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("data", {}).get("list", [])

            if not items:
                return None

            job_infos = []
            for item in items:
                job_info = self._extract_job_info(item, title)
                job_infos.append(job_info)

            return job_infos

        except Exception as e:
            print(f"请求异常（{title} 第 {page} 页）：{str(e)}")
            return None

    def _process_job_title(self, title):
        """处理单个职位名称的爬取任务"""
        print(f"\n开始爬取职位: {title}")
        page = 1
        total_count = 0

        while True:
            job_infos = self._fetch_page(title, page)
            if not job_infos:
                print(f"职位 {title} 共爬取 {page - 1} 页，{total_count} 条数据")
                break

            # 保存去重后的数据
            self._save_unique_jobs(job_infos)

            current_count = len(job_infos)
            total_count += current_count
            print(f"正在爬取 {title} 第 {page} 页，获取 {current_count} 条，累计 {total_count} 条")

            page += 1
            time.sleep(random.uniform(1, 3))  # 控制爬取速度

    def _worker(self):
        """工作线程函数"""
        while True:
            title = self.job_queue.get()
            if title is None:  # 结束信号
                self.job_queue.task_done()
                break

            try:
                self._process_job_title(title)
            except Exception as e:
                print(f"处理职位 {title} 时发生异常: {str(e)}")
                with self.lock:
                    self.stats['failed_jobs'] += 1
            finally:
                self.job_queue.task_done()

    def collect_jobs(self, job_titles):
        """
        多线程爬取职位数据

        :param job_titles: 职位名称列表
        """
        print("===== 开始爬取数据 =====")
        self.stats['total_jobs'] = len(job_titles)
        self.stats['start_time'] = time.time()

        # 启动工作线程
        threads = []
        for _ in range(self.max_workers):
            t = threading.Thread(target=self._worker)
            t.start()
            threads.append(t)

        # 添加任务到队列
        for title in job_titles:
            self.job_queue.put(title)

        # 等待所有任务完成
        self.job_queue.join()

        # 发送结束信号
        for _ in range(self.max_workers):
            self.job_queue.put(None)

        # 等待所有线程结束
        for t in threads:
            t.join()

        # 打印统计信息
        elapsed_time = time.time() - self.stats['start_time']
        print(f"\n所有任务完成！数据已保存到: {self.output_file}")
        print(f"统计信息:")
        print(f"- 总职位数: {self.stats['total_jobs']}")
        print(f"- 成功爬取: {self.stats['success_jobs']}")
        print(f"- 失败爬取: {self.stats['failed_jobs']}")
        print(f"- 耗时: {elapsed_time:.2f}秒")


# 数据存储模块
class DataStorage:
    # 数据清理·
    def clean_text(self,text: str) -> str:
        """终极清理：彻底去除转义字符、多余符号和空元素"""
        # 第一阶段：处理特殊转义字符和空白符
        text = re.sub(r'\\[rnt"]', ' ', text)  # 处理 \r \n \t \" 等转义符
        text = re.sub(r'[\r\n\t]+', ' ', text)  # 再次确保无换行符
        text = re.sub(r'\s+', ' ', text).strip()  # 合并连续空格

        # 第二阶段：清理引号和逗号
        text = re.sub(r"\s*'\s*", "'", text)  # 引号周围空格
        text = re.sub(r"\s*,\s*", ", ", text)  # 逗号规范化

        # 第三阶段：清除空元素和边界符号
        text = re.sub(r",\s*''\s*", "", text)  # 移除空元素
        text = re.sub(r"\[\s*'?", "[", text)  # 处理开头 [ 和 ['
        text = re.sub(r"'\s*\]", "]", text)  # 处理结尾 ']
        text = re.sub(r"\[\s*\]", "[]", text)  # 确保空列表标识保留

        # 第四阶段：最终修正
        text = re.sub(r"'\s*,\s*'", "', '", text)  # 统一列表分隔符格式
        text = re.sub(r",\s*,", ",", text)  # 移除连续逗号
        return text

    # 处理2022年招聘数据
    def load_and_process_2022_data(self,csv_file):
        """
        数据加载和处理函数
        :param csv_file: CSV文件路径
        :return: 处理后的数据列表
        """

        def process_row(row):
            """内部函数：处理单行数据"""
            return {
                "job_title": str(row.get("岗位名称", "")),
                "company_name": str(row.get("公司名称", "")),
                "salary_range": str(row.get("薪资", "")),
                "location": str(row.get("城市", "")),
                "openings": "1",
                "requirements": self.clean_text(str(row.get('职位详情', '')) + str(row.get('基本要求', ''))),
                "search_keyword": str(row.get("公司行业", "")),
                "data_year": 2022
            }

        try:
            # 读取数据
            df = pd.read_csv(csv_file)

            # 处理并返回数据
            return [process_row(row) for _, row in df.iterrows()]

        except FileNotFoundError:
            raise Exception(f"文件未找到: {csv_file}")
        except pd.errors.EmptyDataError:
            raise Exception("CSV文件内容为空")
        except Exception as e:
            raise Exception(f"数据处理失败: {str(e)}")

    # 处理2023年招聘数据
    def load_and_process_2023_data(self,file_path):
        """
        使用pandas从Excel文件读取数据并处理成所需格式（修复NaN问题）

        参数:
            file_path: Excel文件路径

        返回:
            处理后的数据列表，每个元素是一个字典
        """
        # 读取数据并填充空值为空字符串，避免NaN
        df = pd.read_excel(file_path).fillna('')

        processed = []
        for _, row in df.iterrows():
            # 合并关键词和行业信息
            keywords = str(row.get("关键词", "")).replace("\n", ", ")
            industry = str(row.get("int", ""))

            # 提取行业信息的第一部分
            if industry:
                first_part = industry.split()[0] if industry else ""
                requirements = f"{keywords}, 行业: {first_part}" if first_part else keywords
            else:
                requirements = keywords

            # 处理地点字段（避免空字符串split报错）
            d_value = str(row.get("d", ""))
            d_parts = d_value.split()
            location = d_parts[0] if d_parts else ""

            processed_item = {
                "job_title": str(row.get("名称", "")),  # 强制转为字符串
                "company_name": str(row.get("名称3", "")),  # 强制转为字符串
                "salary_range": str(row.get("sal", "")),  # 强制转为字符串
                "location": location,
                "openings": 1,
                "requirements": requirements,
                "search_keyword": str(row.get("int", "")),  # 强制转为字符串
                "data_year": 2023
            }
            processed.append(processed_item)

        return processed

    # 处理2024年招聘数据
    def load_and_process_2024_data(self,csv_file):
        """
        2024版招聘数据处理函数
        :param csv_file: CSV文件路径
        :return: 处理后的数据列表
        """

        def process_row(row):
            """处理单行数据"""
            # 薪资处理（示例：15-25K·13薪 -> 15-25K）
            salary = row.get("薪资", "").split("·")[0]

            return {
                "job_title": row.get("职业名称", ""),
                "company_name": row.get("公司名称", ""),
                "salary_range": salary,
                "location": extract_city(row.get("地址", "")),  # 提取城市
                "openings": "1",
                "requirements": f"{row.get('资历', '')}|{row.get('学历要求', '')}|{row.get('职业简介', '')}",
                "search_keyword": row.get("公司类型", ""),
                "data_year": 2024
            }

        def extract_city(address):
            """从地址字段提取城市"""
            if not address:
                return ""
            # 示例处理逻辑（可根据实际情况调整）
            return address[:2] if len(address) >= 2 else address

        try:
            # 读取数据（指定编码格式）
            df = pd.read_csv(csv_file, encoding='gbk')

            # 处理并返回数据
            return [process_row(row) for _, row in df.iterrows()]

        except FileNotFoundError:
            raise Exception(f"文件未找到: {csv_file}")
        except pd.errors.EmptyDataError:
            raise Exception("CSV文件内容为空")
        except Exception as e:
            raise Exception(f"数据处理失败: {str(e)}")

    # 处理2025年招聘数据
    def load_and_process_2025_data(self,file_path):
        """
        从JSON文件加载数据并进行处理

        参数:
            file_path: JSON文件路径

        返回:
            处理后的数据列表
        """
        processed_data = []

        # 加载并处理JSON数据
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    item = json.loads(line.strip())

                    # 处理工作地点 - 只取第一个字段
                    location = item.get("工作地点", "").split()[0] if item.get("工作地点") else ""

                    # 合并职位要求为一个字符串
                    requirements = ""
                    if "职位要求" in item:
                        req_parts = []
                        if "职位描述" in item["职位要求"]:
                            req_parts.append(item["职位要求"]["职位描述"])
                        if "技能标签" in item["职位要求"]:
                            req_parts.append("技能标签: " + ", ".join(item["职位要求"]["技能标签"]))
                        if "专业技能" in item["职位要求"]:
                            req_parts.append("专业技能: " + ", ".join(item["职位要求"]["专业技能"]))
                        requirements = "\n".join(req_parts)

                    processed_data.append({
                        "job_title": item.get("职位名称", ""),
                        "company_name": item.get("公司名称", ""),
                        "salary_range": item.get("薪资范围", ""),
                        "location": location,
                        "openings": item.get("招聘人数", 0),
                        "requirements": requirements,
                        "search_keyword": item.get("搜索职位", ""),
                        "data_year": 2025
                    })

                except json.JSONDecodeError as e:
                    print(f"解析JSON出错: {e}，行内容: {line}")

        return processed_data

    # 创建数据库中的表
    def create_job_listings_table(self,connection):
        """创建职位信息表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS job_listings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_title VARCHAR(250),
            company_name VARCHAR(250),
            salary_range VARCHAR(100),
            location VARCHAR(100),
            openings INT,
            requirements TEXT,
            search_keyword VARCHAR(100),
            data_year INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(create_table_sql)
            connection.commit()
        # print("表 job_listings 创建成功或已存在")
        except Error as e:
            print(f"创建表失败: {e}")
            raise

    # 数据写入数据库，
    def save_to_database(self, data, db_config):
        """
        :param data: 要存储的数据列表
        param db_config: 数据库配置字典
        """
        connection = None
        try:
            # 建立数据库连接
            connection = pymysql.connect(**db_config)
            # 创建数据表
            self.create_job_listings_table(connection)

            # 执行数据插入
            with connection.cursor() as cursor:
                sql = """INSERT INTO job_listings 
                         (job_title, company_name, salary_range, location, openings, 
                          requirements, search_keyword, data_year) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""

                for item in data:
                    cursor.execute(sql, (
                        item["job_title"],
                        item["company_name"],
                        item["salary_range"],
                        item["location"],
                        item["openings"],
                        item["requirements"],
                        item["search_keyword"],
                        item["data_year"]
                    ))

            connection.commit()
            print(f"成功插入 {len(data)} 条数据")

        except Error as e:
            raise Exception(f"数据库操作失败: {str(e)}")
        finally:
            if connection:
                connection.close()

    # 所有数据分批次存储
    def batch_save_to_database(self,data, batch_size=1000, max_retries=3):
        """
        分批次存储数据到数据库
        :param data: 待存储的数据列表
        :param batch_size: 每批数据量（默认100条）
        :param max_retries: 失败最大重试次数
        """

        def save_batch(batch_data, attempt=1):
            """单批次存储函数"""
            try:
                self.save_to_database(batch_data)
                return True
            except Exception as e:
                if attempt <= max_retries:
                    print(f"批次存储失败，正在重试({attempt}/{max_retries})...")
                    return save_batch(batch_data, attempt + 1)
                print(f"最终存储失败: {str(e)}")
                return False

        # 计算总批次数
        total_batches = math.ceil(len(data) / batch_size)
        success_count = 0  # 成功写入的条数计数器
        # 使用进度条可视化
        with tqdm(total=len(data), desc="数据存储进度") as pbar:
            for i in range(total_batches):
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, len(data))
                batch = data[start_idx:end_idx]

                if save_batch(batch):
                    pbar.update(len(batch))
                    success_count += len(batch)
                else:
                    # 失败处理（可记录到日志或错误列表）
                    print(f"批次 {i + 1} 存储失败，跳过该批次")
            # 打印总数据写入条数
        print(f"数据存储完成，成功写入 {success_count} 条数据")

    def main(self):
        """主处理流程"""
        try:
            # 1. 数据加载
            processed_2022 = self.load_and_process_2022_data('2022年--ICT相关专业招聘数据.csv')
            processed_2023y, processed_2023z = (self.load_and_process_2023_data(f) for f in
                                                ['【新新软件工程师】-前程无忧.xlsx', '【新新硬件工程师】-前程无忧.xlsx'])
            processed_2024 = self.load_and_process_2024_data('2024ICT数据.csv')
            processed_2025 = self.load_and_process_2025_data('raw_data.jsonl')
            # 2. 数据合并（示例去重逻辑）
            all_data = processed_2022 + processed_2023y + processed_2023z + processed_2024 + processed_2025

            # 3. 分批次存储（每批1000条）
            self.batch_save_to_database(all_data, batch_size=1000)

        except Exception as e:
            print(f"流程执行失败: {str(e)}")



# 数据分析模块
class DataAnalyzer:
    def __init__(self):
        # 配置日志记录
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def get_db_connection(self):
        """
        建立数据库连接
        :return: 数据库连接对象或 None（连接失败时）
        """
        try:
            return pymysql.connect(
                host='127.0.0.1',
                user='visitor',
                password='pf123456',
                database='zpsj',
                charset='utf8mb4'
            )
        except pymysql.Error as e:
            logging.error(f"数据库连接出错: {e}")
            return None

    # 从数据库获取对应年份的职位要求数据，返回字符串
    def get_field_from_db(self, data_year):
        """
        从数据库获取指定年份的职位要求数据
        :param data_year: 数据年份
        :return: 职位要求数据字符串
        """
        connection = self.get_db_connection()
        field_text = ""

        try:
            with connection.cursor() as cursor:
                # 执行SQL查询，获取指定字段
                sql = f"SELECT requirements FROM job_listings WHERE data_year = %s"
                cursor.execute(sql, (data_year,))

                # 获取所有结果并拼接成一个大字符串
                results = cursor.fetchall()
                for row in results:
                    if row[0]:  # 确保字段不为空
                        field_text += row[0] + "\n"
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if connection:
                connection.close()

        return field_text

    # jieba分词统计词频并去除无效词语
    def perform_word_segmentation(self, text):
        """
        对输入文本进行jieba分词，统计词频并去除无效词语
        :param text: 输入文本
        :return: 处理后的词语字符串
        """
        if not text:
            print("没有获取到任何数据")
            return
        specific_words = [
            '的', '是', '和', '在',
            '工作', 'xa0', '相关', '能力',
            '要求', '客户', '技能', '行业',
            '标签', '公司', '优先', '进行',
            '需求', '销售', '完成', '...',
            '以上', '岗位职责', '团队', '任职',
            '本科', '具备', '良好', '以上学历',
            '维护', '业务', '具有', '五险',
            '一金', '问题', '设备', '补贴',
            '使用', '方案', '参与', '岗位',
            '大专', '平台', '实施', '提供',
            '职能', '类别', '了解', '根据',
            '员工', '制定', '年终奖金', '解决',
            '定期', '文档', '能够', '包括',
            '处理', '确保', '福利', '绩效奖金',
            '以及', '其他'
        ]
        seg_list = jieba.cut(text, cut_all=False)
        words = " ".join(seg_list)
        words_list = words.split()
        filtered_words = [word for word in words_list if word not in specific_words and len(word) > 1]
        word_counts = Counter(filtered_words)

        top_count = 0
        for word, count in word_counts.most_common(200):
            if len(word) > 1:
                top_count += 1
                if top_count == 100:
                    break
        return " ".join(filtered_words)

    # 根据分词结果绘制词云图
    def generate_wordcloud(self, words, save_path="requirements_wordcloud.png"):
        """
        根据输入词语生成词云图
        :param words: 词语字符串
        :param save_path: 词云图保存路径
        """
        # 基本词云
        wc = WordCloud(
            font_path="simhei.ttf",  # 设置中文字体，否则中文会显示乱码
            background_color="white",  # 背景颜色
            max_words=100,  # 最多显示词数
            max_font_size=100,  # 字体最大值
            width=800,  # 图宽
            height=600,  # 图高
            collocations=False,  # 避免重复词语
        )

        # 生成词云
        wc.generate(words)

        # 显示词云图
        plt.figure(figsize=(10, 8))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")  # 隐藏坐标轴
       #plt.show()

        # 保存词云图
        wc.to_file(save_path)

    # 获取数据库工作地点及招聘人数信息
    def get_data_from_db(self, data_year):
        """
        从数据库获取指定年份的工作地点及招聘人数信息
        :param data_year: 数据年份
        :return: 工作地点及招聘人数信息列表
        """
        connection = self.get_db_connection()
        if not connection:
            return []
        try:
            with connection.cursor() as cursor:
                # 添加时间筛选条件
                sql = "SELECT location, openings FROM job_listings WHERE data_year = %s"
                cursor.execute(sql, (data_year,))
                results = cursor.fetchall()
                data = []
                for row in results:
                    location = row[0]
                    if '-' in location:
                        location = location.split('-')[0]
                    elif '·' in location:
                        location = location.split('·')[0]
                    # 过滤掉外国数据、'全国' 和 '其他' 数据
                    if location and location.lower() != 'nan' and location not in ['全国',
                                                                                   '其他']:
                        data.append((location, int(row[1])))
            return data
        except pymysql.Error as e:
            logging.error(f"数据库查询出错: {e}")
            return []
        finally:
            if connection:
                connection.close()

    # 将数据库中获取的工作地点及招聘人数信息转换成元组
    def process_data(self, data):
        """
        处理工作地点及招聘人数信息，转换为元组形式并合并相同地点的数据
        :param data: 原始数据列表
        :return: 处理后的数据列表
        """
        location_dict = {}
        for location, openings in data:
            if location in location_dict:
                location_dict[location] += openings
            else:
                location_dict[location] = openings
        processed_data = [(location, count) for location, count in location_dict.items()]
        return processed_data

    # 将元组信息工作地点映射为对应省份
    def map_data(self, processed_data):
        """
        将工作地点映射为对应省份
        :param processed_data: 处理后的工作地点及招聘人数数据
        :return: 映射后的工作地点及招聘人数数据
        """
        # 从数据库获取映射关系进行二次映射
        connection = self.get_db_connection()
        if not connection:
            return processed_data
        try:
            with connection.cursor() as cursor:
                # 从数据库中查询城市到省份的映射关系
                sql = "SELECT short_name, full_name FROM city_mapping"
                cursor.execute(sql)
                city_province_mapping = {row[0]: row[1] for row in cursor.fetchall()}

            second_mapped_data = []
            for location, count in processed_data:
                new_location = city_province_mapping.get(location, location)
                # 去除引号
                new_location = new_location.strip('"')
                second_mapped_data.append((new_location, count))

            return second_mapped_data
        except pymysql.Error as e:
            logging.error(f"数据库映射出错: {e}")
            return processed_data
        finally:
            if connection:
                connection.close()

    # 绘制中国各省份招聘岗位热力图
    def generate_province_recruitment_map(self, data_list, year, output_file):
        """
        绘制中国各省份招聘岗位热力图
        :param data_list: 工作地点及招聘人数数据列表
        :param year: 数据年份
        :param output_file: 热力图保存文件路径
        :return: 保存文件路径
        """
        # 合并同一省份的数据
        province_dict = {}
        for location, count in data_list:
            if location in province_dict:
                province_dict[location] += count
            else:
                province_dict[location] = count
        final_data = [(province, count) for province, count in province_dict.items()]

        # 创建Map对象
        map_chart = Map()
        # 添加数据
        map_chart.add("各省份招聘数据", final_data, "china")
        # 设置全局选项
        map_chart.set_global_opts(
            title_opts=TitleOpts(title=f"{year}全国招聘数据"),
            visualmap_opts=VisualMapOpts(
                is_show=True,  # 是否显示
                is_piecewise=True,  # 是否分段
                pieces=[
                    {"min": 0, "max": 9, "label": "1~9人", "color": "#F5DEB3"},
                    {"min": 10, "max": 99, "label": "10~99人", "color": "#F4A460"},
                    {"min": 100, "max": 500, "label": "100~500人", "color": "#D2B48C"},
                    {"min": 501, "max": 1999, "label": "501~1999人", "color": "#D2691E"},
                    {"min": 2000, "label": "2000~20000人", "color": "#B22222"},
                ]
            )
        )
        # 渲染地图到HTML文件
        map_chart.render(output_file)
        return output_file

    # 绘制热力图
    def generate_job_distribution_heatmap(self, data, output_file="job_distribution_heatmap.html"):
        """
        绘制中国各地区招聘岗位分布热力图
        :param data: 工作地点及招聘人数数据列表
        :param output_file: 热力图保存文件路径
        """
        try:
            geo = (
                Geo(init_opts=opts.InitOpts(width="1200px", height="800px"))
               .add_schema(
                    maptype="china",  # 因为只展示国内数据，所以地图类型改为中国
                    itemstyle_opts=opts.ItemStyleOpts(color="#ffffff", border_color="#111"),
                )
            )
            # 手动添加国内特殊地区坐标
            custom_coords = {
                "克孜勒苏柯尔克孜自治州": [76.1889, 39.7062]
            }
            for location, _ in data:
                if location in custom_coords:
                    geo.add_coordinate(location, *custom_coords[location])

            geo.add(
                "招聘岗位分布",
                data,
                type_=ChartType.HEATMAP,
                label_opts=opts.LabelOpts(is_show=False),
            )
            geo.set_global_opts(
                title_opts=opts.TitleOpts(title="中国各地区招聘岗位分布热力图"),
                visualmap_opts=opts.VisualMapOpts(
                    min_=0,
                    max_=max([item[1] for item in data]) if data else 100,
                    is_piecewise=True,
                    range_color=["#50a3ba", "#eac736", "#d94e5d"],
                ),
            )

            # 生成 HTML 文件
            geo.render(output_file)
            print(f"文件已成功生成: {output_file}")
        except Exception as e:
            import traceback
            print(f"生成图表或保存文件时出错: {e}")
            traceback.print_exc()

    # 从数据库获取薪资数据
    def get_salary_data(self, year):
        """
        从数据库获取指定年份的薪资数据
        :param year: 数据年份
        :return: 薪资数据列表
        """
        connection = self.get_db_connection()
        if not connection:
            return []

        try:
            with connection.cursor() as cursor:
                # 修改 SQL 查询语句，增加对 data_year 字段的筛选
                cursor.execute("SELECT salary_range FROM job_listings WHERE data_year = %s", (year,))
                return [row[0] for row in cursor.fetchall()]
        except pymysql.Error as e:
            logging.error(f"数据查询异常: {e}")
            return []
        finally:
            if connection:
                connection.close()

    # 处理获取的薪资数据
    def parse_salary(self, salary_str):
        """
        解析薪资格式，将各种格式的薪资转换为月薪数值
        :param salary_str: 薪资格式字符串
        :return: 月薪数值或 None（无法解析时）
        """
        # 空值处理
        if isinstance(salary_str, float) and math.isnan(salary_str):
            return None
        salary_str = str(salary_str).strip()
        if salary_str == 'nan' or salary_str == "":
            return None

        # 预设参数
        work_days_per_month = 21.75  # 月平均工作日
        work_hours_per_day = 8  # 每日工作时长

        # 处理 "面议" 的情况
        if salary_str == "面议":
            return None

        # 解析优先级从高到低排列

        # 1. 处理时薪（如"21元/小时"）
        if '元/小时' in salary_str:
            if match := re.match(r'(\d+\.?\d*)元/小时', salary_str):
                hourly = float(match.group(1))
                monthly = hourly * work_hours_per_day * work_days_per_month
                return round(monthly, 2)

        # 处理新的时薪格式（如 "10-25元/时" 和单个金额的 "300元/时"）
        if '元/时' in salary_str:
            if re.search(r'(\d+\.?\d*)-(\d+\.?\d*)元/时', salary_str):
                match = re.match(r'(\d+\.?\d*)-(\d+\.?\d*)元/时', salary_str)
                lower = float(match.group(1))
                upper = float(match.group(2))
                monthly = (lower + upper) / 2 * work_hours_per_day * work_days_per_month
                return round(monthly, 2)
            elif match := re.match(r'(\d+\.?\d*)元/时', salary_str):
                hourly = float(match.group(1))
                monthly = hourly * work_hours_per_day * work_days_per_month
                return round(monthly, 2)

        # 2. 处理日薪（如"200元/天"）
        if '元/天' in salary_str:
            if match := re.match(r'(\d+\.?\d*)元/天', salary_str):
                daily = float(match.group(1))
                return daily * work_days_per_month

        # 处理新的日薪格式（如 "60-100元/天"、"150-200元/天" 等）
        if re.search(r'\d+-\d+元/天', salary_str):
            if match := re.match(r'(\d+\.?\d*)-(\d+\.?\d*)元/天', salary_str):
                lower = float(match.group(1))
                upper = float(match.group(2))
                return (lower + upper) / 2 * work_days_per_month

        # 3. 处理特殊月薪（如"10万以上/月"）
        if '以上/月' in salary_str:
            if match := re.match(r'(\d+\.?\d*)(万|千)以上/月', salary_str):
                value, unit = match.groups()
                multiplier = 10000 if unit == '万' else 1000
                return float(value) * multiplier

        # 处理特殊年薪（如"100万以上/年"）
        if '以上/年' in salary_str:
            if match := re.match(r'(\d+\.?\d*)(万|千)以上/年', salary_str):
                value, unit = match.groups()
                multiplier = 10000 if unit == '万' else 1000
                return float(value) * multiplier / 12

        # 4. 处理带年终奖的复合格式（如"1.5-2.5万·13薪"）
        if '·' in salary_str:
            parts = salary_str.split('·')
            if len(parts) == 2 and '薪' in parts[1]:
                main_salary = self.parse_salary(parts[0])
                if main_salary is not None:
                    if bonus_match := re.match(r'(\d+)薪', parts[1]):
                        return main_salary * int(bonus_match.group(1)) / 12

        # 处理新的带年终奖且单位为元的格式（如 "8000-16000元·13薪"）
        if re.search(r'\d+-\d+元·\d+薪', salary_str):
            parts = salary_str.split('·')
            if len(parts) == 2 and '薪' in parts[1]:
                if match := re.match(r'(\d+)-(\d+)元', parts[0]):
                    lower = float(match.group(1))
                    upper = float(match.group(2))
                    main_salary = (lower + upper) / 2
                    if bonus_match := re.match(r'(\d+)薪', parts[1]):
                        return main_salary * int(bonus_match.group(1)) / 12

        # 5. 处理带时间单位的范围薪资（如"1.1-1.8万/月"）
        range_pattern_month = r'''
            ^
            ([\d.]+)    # 起始值
            -
            ([\d.]+)    # 结束值
            (万|千)     # 单位
            /月
        '''
        if match := re.match(range_pattern_month, salary_str, re.VERBOSE):
            lower, upper, unit = match.groups()
            multiplier = 10000 if unit == '万' else 1000
            return (float(lower) * multiplier + float(upper) * multiplier) / 2

        # 处理新的月薪格式（如 "10000-15000元/月"）
        if re.search(r'\d+-\d+元/月', salary_str):
            if match := re.match(r'(\d+)-(\d+)元/月', salary_str):
                lower = float(match.group(1))
                upper = float(match.group(2))
                return (lower + upper) / 2

        # 处理无时间单位且单位为元的薪资范围（如 "6000-10000元"）
        if re.search(r'\d+-\d+元', salary_str):
            if match := re.match(r'(\d+)-(\d+)元', salary_str):
                lower = float(match.group(1))
                upper = float(match.group(2))
                return (lower + upper) / 2

        # 处理固定金额的薪资，单位为“元”或“万”（如 "1万"、"5000元"）
        if re.search(r'\d+万', salary_str):
            if match := re.match(r'(\d+)万', salary_str):
                value = float(match.group(1))
                return value * 10000
        elif re.search(r'\d+元', salary_str):
            if match := re.match(r'(\d+)元', salary_str):
                return float(match.group(1))

        # 处理带有上下限描述的固定金额薪资（如 "1000元以下"）
        if re.search(r'\d+元(以下|以上)', salary_str):
            if match := re.match(r'(\d+)元(以下|以上)', salary_str):
                value = float(match.group(1))
                direction = match.group(2)
                if direction == "以下":
                    return value * 0.8
                elif direction == "以上":
                    return value * 1.2

        # 6. 处理按年计算的范围薪资（如 "15-25万/年"）
        range_pattern_year = r'''
            ^
            ([\d.]+)    # 起始值
            -
            ([\d.]+)    # 结束值
            (万|千)     # 单位
            /年
        '''
        if match := re.match(range_pattern_year, salary_str, re.VERBOSE):
            lower, upper, unit = match.groups()
            multiplier = 10000 if unit == '万' else 1000
            return (float(lower) * multiplier + float(upper) * multiplier) / 12

        # 7. 处理无时间单位的范围薪资（如"1.5-3万"）
        range_pattern_no_time = r'''
            ^
            ([\d.]+)    # 起始值
            -
            ([\d.]+)    # 结束值
            (万|千)     # 单位
            (?!/)       # 排除有时间单位的情况
        '''
        if match := re.match(range_pattern_no_time, salary_str, re.VERBOSE):
            lower, upper, unit = match.groups()
            multiplier = 10000 if unit == '万' else 1000
            return (float(lower) * multiplier + float(upper) * multiplier) / 2

        # 处理以K为单位的薪资范围（如 "3-4K"）
        k_range_pattern = r'^(\d+\.?\d*)-(\d+\.?\d*)K$'
        if match := re.match(k_range_pattern, salary_str):
            lower = float(match.group(1)) * 1000
            upper = float(match.group(2)) * 1000
            return (lower + upper) / 2

        # 处理不同单位的范围薪资（如 "8千 - 1.6万"）
        diff_unit_range_pattern = r'^(\d+\.?\d*)(千)-(\d+\.?\d*)(万)$'
        if match := re.match(diff_unit_range_pattern, salary_str):
            lower = float(match.group(1)) * 1000
            upper = float(match.group(3)) * 10000
            return (lower + upper) / 2

        # 8. 处理上下限薪资（如"1.5千以下/月"）
        limit_pattern = r'''
            ^
            ([\d.]+)    # 数值
            (万|千)     # 单位
            (以下|以上)  # 限定方向
            /月
        '''
        if match := re.match(limit_pattern, salary_str, re.VERBOSE):
            value, unit, direction = match.groups()
            multiplier = 10000 if unit == '万' else 1000
            base = float(value) * multiplier
            # 根据方向调整估值
            return base * (0.8 if direction == '以下' else 1.2)

        logging.warning(f"无法识别的薪资格式: {salary_str}")
        return None

    # 生成薪资分布直方图
    # def p_salary_distribution(self, salaries, year, should_plot_kde=True):
    #     """
    #     生成薪资分布直方图和薪资分布曲线
    #     :param salaries: 薪资数据列表
    #     :param year: 数据年份
    #     :param should_plot_kde: 是否绘制薪资分布曲线
    #     """
    #     # 数据清洗
    #     parsed = [s for s in (self.parse_salary(x) for x in salaries) if s is not None]
    #
    #     # 薪资合理性过滤
    #     valid = [s for s in parsed if 1500 <= s <= 150000]  # 扩展合理范围
    #
    #     if not valid:
    #         print("无有效数据可供可视化")
    #         return
    #
    #     # 动态分箱策略
    #     q95 = np.percentile(valid, 95)
    #     bins = np.linspace(
    #         max(2000, np.percentile(valid, 5)),  # 排除最低5%
    #         min(q95, 100000),  # 排除超过95%的高薪
    #         num=min(20, len(valid) // 10)  # 自适应分箱数量
    #     )
    #
    #     # 可视化设置
    #     plt.figure(figsize=(14, 7))
    #     n, bins, patches = plt.hist(
    #         valid,
    #         bins=bins,
    #         edgecolor='white',
    #         color='#2196F3',
    #         alpha=0.85
    #     )
    #
    #     # 添加薪资分布曲线
    #     if should_plot_kde:
    #         kde = gaussian_kde(valid)
    #         x = np.linspace(bins[0], bins[-1], 500)
    #         plt.plot(x, kde(x) * len(valid) * np.diff(bins)[0],
    #                  color='#FF5722',
    #                  linewidth=2,
    #                  label='分布曲线')
    #
    #     # 高级格式化
    #     ax = plt.gca()
    #     ax.xaxis.set_major_formatter(plt.FuncFormatter(
    #         lambda x, _: f'{x / 10000:.1f}万' if x >= 10000 else f'{int(x)}元'))
    #     plt.xticks(rotation=45)
    #
    #     # 添加统计信息
    #     stats_text = f"""统计摘要（{datetime.now().strftime('%Y-%m-%d')}）:
    #     - 有效样本: {len(valid):,}
    #     - 中位月薪: {np.median(valid):,.0f}元
    #     - 平均月薪: {np.mean(valid):,.0f}元
    #     - 主要区间: {np.percentile(valid, 25):,.0f} - {np.percentile(valid, 75):,.0f}元"""
    #
    #     plt.annotate(stats_text, xy=(0.68, 0.72), xycoords='axes fraction',
    #                  bbox=dict(boxstyle="round", fc="white", alpha=0.9),
    #                  fontsize=10)
    #
    #     plt.title(f"{year}企业薪资分布分析报告", fontsize=16, pad=20)
    #     plt.xlabel('月薪（人民币）', fontsize=12)
    #     plt.ylabel('职位数量', fontsize=12)
    #     # y轴方向添加网格线,透明都为0.3
    #     plt.grid(axis='y', alpha=0.3)
    #     # 用于在当前绘图区域添加图例
    #     plt.legend()
    #     # 代码的作用是自动调整子图参数，保证子图之间以及子图与绘图区域边缘之间有合适的间距，避免出现元素重叠的情况，从而使绘图布局更加紧凑、美观。
    #     plt.tight_layout()
    #     # 保存图片
    #     plt.savefig(f"{year}_salary_distribution.png", dpi=300)
    #     # plt.show()

    # 生成薪资分布扇形图
    def plot_salary_distribution(self, salaries, year):
        """增强版可视化函数"""
        # 数据清洗
        parsed = [s for s in (self.parse_salary(x) for x in salaries) if s is not None]

        # 薪资合理性过滤
        valid = [s for s in parsed if 1500 <= s <= 150000]  # 扩展合理范围

        if not valid:
            print("无有效数据可供可视化")
            return

        # 分箱处理，设置更细致的薪资范围
        bins = [1500, 3000, 5000, 8000, 12000, 18000, 25000, 150000]
        counts, _ = np.histogram(valid, bins=bins)

        # 区间标签，对应每个薪资范围
        labels = [
            '1500-3000元', '3000-5000元', '5000-8000元',
            '8000-12000元', '12000-18000元', '18000-25000元',
            '25000元以上'
        ]

        # 生成标签文本，包含区间和百分比
        label_texts = [f"{label} ({count / len(valid) * 100:.1f}%)"
                       for label, count in zip(labels, counts) if count > 0]

        # 过滤零值区间
        filtered_counts = [count for count in counts if count > 0]

        # 可视化设置
        plt.rcParams['font.family'] = 'SimHei'  # 设置为黑体
        plt.figure(figsize=(12, 8))
        wedges, texts, autotexts = plt.pie(
            filtered_counts,
            labels=label_texts if len(label_texts) > 0 else None,
            autopct='%1.1f%%',
            startangle=140,
            pctdistance=0.8,
            labeldistance=1.05,
            colors=plt.cm.Paired.colors
        )

        # 调整文本样式
        for text in texts:
            text.set_color('darkblue')
            text.set_fontsize(10)

        # 添加统计信息（右侧）
        stats_text = f"""统计摘要（{datetime.now().strftime('%Y-%m-%d')}）:
        - 有效样本: {len(valid):,}
        - 中位月薪: {np.median(valid):,.0f}元
        - 平均月薪: {np.mean(valid):,.0f}元
        - 主要区间: {np.percentile(valid, 25):,.0f} - {np.percentile(valid, 75):,.0f}元"""

        plt.text(1.3, 0.5, stats_text, transform=plt.gca().transAxes,
                 bbox=dict(boxstyle="round", fc="white", alpha=0.9),
                 fontsize=10, ha='left', va='center')

        # 添加图例
        plt.legend(wedges, labels,
                   loc="center left",
                   bbox_to_anchor=(0.8, 0, 0.5, 1),
                   fontsize=9)

        plt.title(f'{year}薪资分布分析报告', fontsize=16, pad=20)
        #使坐标轴的刻度等长，确保图形在屏幕上的显示比例与数据的实际比例一致。
        plt.axis('equal')
        #自动调整子图参数，使子图填充整个图像区域，避免标签重叠。
        plt.tight_layout()
        # 保存图片
        plt.savefig(f"{year}_salary_distribution.png", dpi=300)
        #plt.show()

    # 控制生成2022到2025的词云图及热力图
    def process_year(self, year):
        """
        处理指定年份的数据，生成词云图、省份招聘热力图和薪资分布图
        :param year: 数据年份
        """
        # 绘制词云图
        field_data1 = self.get_field_from_db(year)
        words = self.perform_word_segmentation(field_data1)
        self.generate_wordcloud(words, f"{year}_wordcloud.png")
        # 绘制热力图
        data = self.get_data_from_db(year)
        processed_data = self.process_data(data)
        mapped_data = self.map_data(processed_data)
        self.generate_province_recruitment_map(mapped_data, year, f"{year}.html")
        # 绘制薪资分布图
        salary = self.get_salary_data(year)
        if salary:
            self.plot_salary_distribution(salary, year)




# GUI界面模块
class DataAnalyzerApp(DataAnalyzer):
    def __init__(self, root):
        self.root = root
        self.setup_ui()
        self.current_chart_type = None
        # 存储不同类型和年份对应的图片路径
        self.image_paths = {
            ("wordcloud", 2022): "2022_wordcloud.png",
            ("wordcloud", 2023): "2023_wordcloud.png",
            ("wordcloud", 2024): "2024_wordcloud.png",
            ("wordcloud", 2025): "2025_wordcloud.png",
            ("wordcloud", "all"): "2022 - 2025_wordcloud.png",
            ("heatmap", 2022): "2022.jpg",
            ("heatmap", 2023): "2023.jpg",
            ("heatmap", 2024): "2024.jpg",
            ("heatmap", 2025): "2025.jpg",
            ("heatmap", "all"): "all.jpg",
            ("salary_distribution", 2022): "2022_salary_distribution.png",
            ("salary_distribution", 2023): "2023_salary_distribution.png",
            ("salary_distribution", 2024): "2024_salary_distribution.png",
            ("salary_distribution", 2025): "2025_salary_distribution.png",
            ("salary_distribution", "all"): "2022-2025_salary_distribution.png",
        }

    def setup_ui(self):
        # 设置窗口标题和大小
        self.root.title("ICT相关招聘数据分析系统")

        # 获取屏幕尺寸并设置窗口大小
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = int(screen_width * 0.5)
        window_height = int(screen_height * 0.8)
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.resizable(False, False)

        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建选项卡控件
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 创建岗位信息选项卡
        self.job_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.job_frame, text="岗位信息查询统计")
        self.setup_job_tab()

        # 创建可视化图表选项卡
        self.visualization_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.visualization_frame, text="数据可视化")
        self.setup_visualization_tab()

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X)

    def setup_visualization_tab(self):
        # 使用grid布局管理可视化选项卡内组件
        self.visualization_frame.grid_rowconfigure(0, weight=0)  # 年份按钮行权重
        self.visualization_frame.grid_rowconfigure(1, weight=0)  # 图表类型按钮行权重
        self.visualization_frame.grid_rowconfigure(2, weight=1)  # 图片展示区域行权重

        # 图表选择按钮区域
        button_frame = ttk.Frame(self.visualization_frame)
        button_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)

        ttk.Button(button_frame, text="技能词云图", command=lambda: self.show_year_buttons("wordcloud")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="岗位热力分布图", command=lambda: self.show_year_buttons("heatmap")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="薪资分布图", command=lambda: self.show_year_buttons("salary_distribution")).pack(
            side=tk.LEFT, padx=5)

        # 年份选择按钮框架
        self.year_button_frame = ttk.Frame(self.visualization_frame)
        self.year_button_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # 年份按钮
        years = [2022, 2023, 2024, 2025, "all"]
        col = 0
        for year in years:
            ttk.Button(self.year_button_frame, text=str(year), command=lambda y=year: self.show_chart_by_year(y)).grid(
                row=0, column=col, padx=5)
            col += 1

        # 图片显示区域
        self.image_frame = ttk.LabelFrame(self.visualization_frame, text="图表展示", padding="10")
        self.image_frame.grid(row=2, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.image_frame.grid_propagate(False)
        self.image_frame.rowconfigure(0, weight=1)
        self.image_frame.columnconfigure(0, weight=1)

        # 动态调整宽度为父容器的宽度
        def update_image_frame_width(event):
            parent_width = self.visualization_frame.winfo_width()
            self.image_frame.config(width=parent_width - 20)  # 减去内边距

        # 绑定父容器的大小变化事件
        self.visualization_frame.bind("<Configure>", update_image_frame_width)

        self.image_label = ttk.Label(self.image_frame)
        self.image_label.grid(row=0, column=0, sticky=tk.NSEW)

    def show_year_buttons(self, chart_type):
        self.current_chart_type = chart_type
        self.year_button_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        # 确保图表类型按钮所在的框架不会被覆盖
        self.visualization_frame.grid_rowconfigure(0, weight=0)
        self.visualization_frame.grid_rowconfigure(1, weight=0)
        self.visualization_frame.grid_rowconfigure(2, weight=1)
    #图片显示按钮控制
    def show_chart_by_year(self, year):
        if self.current_chart_type == "wordcloud":
            image_path = self.image_paths.get(("wordcloud", year), "")
            if not image_path:
                self.status_var.set(f"未找到 {year} 年的技能词云图")
                return
            self.display_image(image_path)
            self.status_var.set(f"显示 {year} 技能词云图")
        elif self.current_chart_type == "heatmap":
            image_path = self.image_paths.get(("heatmap", year), "")
            if not image_path:
                self.status_var.set(f"未找到 {year} 年的岗位热力分布图")
                return
            self.display_image(image_path)
            self.status_var.set(f"显示 {year} 岗位热力分布图")
        elif self.current_chart_type == "salary_distribution":
            image_path = self.image_paths.get(("salary_distribution", year), "")
            if not image_path:
                self.status_var.set(f"未找到 {year} 年的薪资分布图")
                return
            self.display_image(image_path)
            self.status_var.set(f"显示 {year} 薪资分布图")
    #图片显示
    def display_image(self, image_path):
        try:
            # 打开图片
            img = Image.open(image_path)
            # 获取显示区域大小
            frame_width = self.image_frame.winfo_width() - 20
            #print(frame_width)
            frame_height = self.image_frame.winfo_height() - 20
            #print(frame_height)

            # 计算图片的原始宽高比
            original_ratio = img.width / img.height

            # 计算显示区域的宽高比
            frame_ratio = frame_width / frame_height

            # 根据宽高比调整图片大小
            if original_ratio > frame_ratio:
                # 图片更宽，按宽度缩放
                new_width = frame_width
                new_height = int(frame_width / original_ratio)
            else:
                # 图片更高，按高度缩放
                new_height = frame_height
                new_width = int(frame_height * original_ratio)

            # 调整图片大小
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            # 更新标签
            self.image_label.configure(image=photo)
            self.image_label.image = photo
        except Exception as e:
            self.status_var.set(f"错误: {str(e)}")
            try:
                img = Image.open(self.default_image_path)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.image_label.configure(image=photo)
                self.image_label.image = photo
            except:
                self.image_label.configure(text="无法加载图片", foreground="red")

    def setup_job_tab(self):
        # 岗位信息查询区域
        job_search_frame = ttk.LabelFrame(self.job_frame, text="岗位查询条件", padding="10")
        job_search_frame.pack(fill=tk.X, padx=5, pady=5)

        # 查询条件输入
        ttk.Label(job_search_frame, text="职业名称:").grid(row=0, column=0, sticky=tk.W)
        self.job_name_combobox = ttk.Combobox(job_search_frame,
                                              values=['ICT工程师', 'ICT项目经理', 'ICT产品经理', '5G工程师', 'ICT',
                                                      '网络工程师', '通信工程师', '云计算工程师', '大数据分析师',
                                                      'ICT测试工程师', '系统工程师', '解决方案架构师', '系统集成工程师',
                                                      '网络与通信', '云计算', '数据中心', '软件开发', '物联网',
                                                      '智能硬件'])
        self.job_name_combobox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(job_search_frame, text="薪资范围:").grid(row=1, column=0, sticky=tk.W)
        self.salary_min = ttk.Entry(job_search_frame, width=10)
        self.salary_min.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(job_search_frame, text="-").grid(row=1, column=2)
        self.salary_max = ttk.Entry(job_search_frame, width=10)
        self.salary_max.grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(job_search_frame, text="工作地点:").grid(row=2, column=0, sticky=tk.W)
        self.location_entry = ttk.Entry(job_search_frame, width=30)
        self.location_entry.grid(row=2, column=1, padx=5, pady=5)

        # 查询按钮
        ttk.Button(job_search_frame, text="查询", command=self.search_jobs).grid(row=3, column=0, columnspan=4, pady=10)

        # 岗位信息显示表格
        job_result_frame = ttk.LabelFrame(self.job_frame, text="查询结果", padding="10")
        job_result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("职位名称", "公司名称", "薪资", "地点")
        self.job_tree = ttk.Treeview(job_result_frame, columns=columns, show="headings", height=10)

        for col in columns:
            self.job_tree.heading(col, text=col)
            self.job_tree.column(col, width=100, anchor=tk.CENTER)

        self.job_tree.pack(fill=tk.BOTH, expand=True)

        # 统计按钮区域
        job_stats_frame = ttk.Frame(self.job_frame)
        job_stats_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(job_stats_frame, text="薪资统计", command=self.show_salary_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(job_stats_frame, text="岗位数量统计", command=self.show_job_count_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(job_stats_frame, text="导出数据", command=self.export_job_data).pack(side=tk.RIGHT, padx=5)
    #岗位查询逻辑
    def search_jobs(self):
        location = self.location_entry.get()
        search_keyword = self.job_name_combobox.get()
        salary_min = self.salary_min.get()
        salary_max = self.salary_max.get()

        try:
            min_value = float(salary_min) if salary_min else float('-inf')
            max_value = float(salary_max) if salary_max else float('inf')
        except ValueError:
            self.status_var.set("薪资输入格式错误，请输入数字")
            return

        self.status_var.set("正在查询岗位信息...")

        db_results = self.query_job_listings(location, search_keyword)

        sample_data = []
        for job in db_results:
            job_title, company_name, salary_str, job_location = job  # 避免变量名冲突
            parsed_salary = super().parse_salary(salary_str)

            try:
                salary_val = float(parsed_salary)
            except (ValueError, TypeError):
                # 如果转换失败，跳过该岗位
                continue

            # 判断薪资是否在用户指定范围内
            if min_value <= salary_val <= max_value:
                sample_data.append(job)

        # 清空现有数据并插入新数据
        self.job_tree.delete(*self.job_tree.get_children())
        for data in sample_data:
            self.job_tree.insert("", tk.END, values=data)

        self.status_var.set(f"找到 {len(sample_data)} 条符合条件的岗位信息")

    def query_job_listings(self,db_config,location="", search_keyword="", salary_range="", data_year=2025):
        try:
            # 建立数据库连接
            # 建立数据库连接
            connection = pymysql.connect(**db_config)

            # 创建游标对象
            with connection.cursor() as cursor:
                conditions = []
                values = []

                if location:
                    location = f"%{location}%"
                    conditions.append("location LIKE %s")
                    values.append(location)

                if search_keyword:
                    search_keyword = f"%{search_keyword}%"
                    conditions.append("job_title LIKE %s")
                    values.append(search_keyword)

                if salary_range:
                    conditions.append("salary_range = %s")
                    values.append(salary_range)

                conditions.append("data_year = %s")
                values.append(data_year)

                # 构建 SQL 查询语句，仅选择所需的列
                query = "SELECT job_title, company_name, salary_range, location FROM job_listings"
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                # 执行查询
                cursor.execute(query, values)

                # 获取查询结果
                results = cursor.fetchall()

                return results
        except pymysql.Error as e:
            print(f"数据库查询出错: {e}")
        finally:
            if connection:
                connection.close()

    def show_salary_stats(self):
        # 显示薪资统计信息
        self.status_var.set("显示薪资统计信息")
        # 这里应该实现实际的统计逻辑

    def show_job_count_stats(self):
        # 显示岗位数量统计
        self.status_var.set("显示岗位数量统计")
        # 这里应该实现实际的统计逻辑

    def export_job_data(self):
        # 导出岗位数据
        self.status_var.set("导出岗位数据")
        # 这里应该实现实际的导出逻辑



# 主控制类（可选）
# class MainController:
#     def __init__(self):
#         self.fetcher = JobDataCollector()
#         self.storage = DataStorage()
#         self.analyzer = DataAnalyzer()
#         self.gui = DataAnalyzerApp(self.analyzer)
#         pass

if __name__ == "__main__":
    #从智联招聘api接口获取数据，已生成jobs_data.jsonl，无需启用
   # collector = JobDataCollector(output_file='jobs_data.jsonl')
    #collector.collect_jobs(['土建工程师', '结构工程师', '土木工程师'])
    # 定义数据库配置
    db_config = {
        'host': '127.0.0.1',
        'user': 'visitor',
        'password': 'pf123456',
        'database': 'zpsj',
        'charset': 'utf8mb4'
    }
    #数据写入数据库，运行一次后注释，防止重复写入
    #storage = DataStorage()
    #storage.main()
    #数据分析
    analyzer = DataAnalyzer()
    # 遍历2022 - 2025年招聘数据，生成招聘要求词云图,省份热力图,薪资分布图
    for year in range(2022, 2026):
        analyzer.process_year(year) #process_year是DataAnalyzer中总控制函数
        #热力图生成HTML文件，手动打开截图后使用
    # 获取2022到2025年的数据
    word_data = ""
    salary_data = []
    for year in range(2022, 2026):
        field_data = analyzer.get_field_from_db(year)
        word_data += field_data
        salarys = analyzer.get_salary_data(year)
        salary_data.extend(salarys)
    #生成2022-2025词云图，薪资分布图，区域热力图
    words = analyzer.perform_word_segmentation(word_data)
    analyzer.generate_wordcloud(words, f"2022 - 2025_wordcloud.png")
    analyzer.plot_salary_distribution(salary_data, year="2022 - 2025")
    #界面展示
    root = tk.Tk()  #创建了一个 Tkinter 应用程序的主窗口
    app = DataAnalyzerApp(root)
    root.mainloop()
