import pandas as pd
from pymysql import Error
import json
from tqdm import tqdm
import pymysql
import re
import math


# 数据存储模块
class DataStorage:
    class DataStorage:
        def __init__(self, config_loader):  # 新增config_loader参数
            self.config_loader = config_loader  # 保存配置加载器

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

    # 修改数据加载逻辑，从配置文件获取路径
    def main(self):
        try:
            # **关键修改：通过config_loader获取文件路径**
            # 2022年数据
            file_2022 = self.config_loader.get_data_file(2022)
            processed_2022 = self.load_and_process_2022_data(file_2022) if file_2022 else []

            # 2023年数据（多个文件）
            files_2023 = self.config_loader.get_data_file(2023)
            processed_2023 = [self.load_and_process_2023_data(f) for f in files_2023] if files_2023 else []
            processed_2023y, processed_2023z = processed_2023 if len(processed_2023) >= 2 else ([], [])

            # 2024年数据
            file_2024 = self.config_loader.get_data_file(2024)
            processed_2024 = self.load_and_process_2024_data(file_2024) if file_2024 else []

            # 2025年数据
            file_2025 = self.config_loader.get_data_file(2025)
            processed_2025 = self.load_and_process_2025_data(file_2025) if file_2025 else []

            # 合并数据（示例去重逻辑）
            all_data = processed_2022 + processed_2023y + processed_2023z + processed_2024 + processed_2025

            # 分批次存储
            self.batch_save_to_database(all_data, batch_size=1000)

        except Exception as e:
            print(f"流程执行失败: {str(e)}")

