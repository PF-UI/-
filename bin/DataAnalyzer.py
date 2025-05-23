import os
import time

import pymysql
import logging
import matplotlib.pyplot as plt
import re
import math
import numpy as np
from datetime import datetime
import jieba
from pyecharts.options import TitleOpts, VisualMapOpts
from scipy.stats import gaussian_kde
from wordcloud import WordCloud
from collections import Counter
from pyecharts import options as opts
from pyecharts.charts import Geo, Map
from pyecharts.globals import ChartType






# 数据分析模块
class DataAnalyzer:
    def __init__(self, config_loader):
        self.config_loader = config_loader
        # 直接访问 config_loader 的 db_config 属性（非方法）
        self.db_config = config_loader.db_config  # 替换原有行
        self.wordcloud_config = config_loader.get_analyzer_config().get('wordcloud', {})
        self.heatmap_config = config_loader.get_analyzer_config().get('heatmap', {})

        # 初始化日志
        self.logger = logging.getLogger(__name__)
        self.config_loader.setup_logging(__name__)
        self.logger.info("数据分析模块初始化完成")

    def get_db_connection(self):
        """建立数据库连接（确保所有必要参数存在）"""
        try:
            # 确保所有必要的连接参数都存在
            connection_params = {
                'host': self.db_config.get('host', 'localhost'),
                'user': self.db_config.get('user', ''),
                'password': self.db_config.get('password', ''),
                'database': self.db_config.get('database', ''),
                'charset': self.db_config.get('charset', 'utf8mb4'),
            }

            print(f"尝试连接数据库: {connection_params}")
            return pymysql.connect(**connection_params)
        except pymysql.Error as e:
            self.logger.error(f"数据库连接出错: {e}")
            return None

    # jieba分词统计词频并去除无效词语
    def perform_word_segmentation(self, text):
        """分词并过滤无效词语（从配置获取stop_words）"""
        if not text:
            self.logger.warning("没有获取到任何数据")
            return ""

        stop_words = self.wordcloud_config.get('stop_words', [])
        seg_list = jieba.cut(text, cut_all=False)
        words_list = [word for word in seg_list if word not in stop_words and len(word) > 1]

        # 限制词云数量（从配置获取max_words）
        word_counts = Counter(words_list)
        top_words = [word for word, _ in word_counts.most_common(self.wordcloud_config.get('max_words', 100))]
        return " ".join(top_words)

    # 根据分词结果绘制词云图
    def generate_wordcloud(self, words, filename=None):
        """生成词云图（从配置获取保存路径和参数）"""
        save_path = self.wordcloud_config.get('image_save_path')
        if not filename:
            filename = f"{datetime.now().strftime('%Y%m%d')}_wordcloud.png"
        full_path = os.path.join(save_path, filename)

        # 新增：保存前200个单词到文本文件
        words_list = words.split()  # 假设words是空格分隔的字符串
        top_200 = words_list[:200] if len(words_list) > 200 else words_list

        txt_filename = f"result/wordcloud/{int(time.time() * 1000)}_wordcloud.txt"
        txt_path = os.path.join("result/wordcloud", txt_filename)

        os.makedirs(os.path.dirname(txt_path), exist_ok=True)  # 确保目录存在
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(top_200))
        self.logger.info(f"前200个单词已保存至: {txt_path}")

        wc = WordCloud(
            font_path=self.wordcloud_config.get('font_path', 'simhei.ttf'),
            background_color="white",
            max_words=self.wordcloud_config.get('max_words', 100),
            width=self.wordcloud_config.get('width', 800),
            height=self.wordcloud_config.get('height', 600),
            collocations=False,
        )
        wc.generate(words)
        wc.to_file(full_path)
        self.logger.info(f"词云图已保存至: {full_path}")

    # 绘制中国各省份招聘岗位热力图
    def generate_province_recruitment_map(self, data_list, year, output_file=None):
        """生成热力图（从配置获取分段颜色）"""
        if not output_file:
            output_file = os.path.join(
                self.heatmap_config.get('result/heatmap/image_save_path'),
                f"{year}_heatmap.heatmap"
            )

        pieces = self.heatmap_config.get('pieces', [])  # 从配置获取分段配置

        map_chart = Map()
        map_chart.add("各省份招聘数据", data_list, "china")
        map_chart.set_global_opts(
            title_opts=TitleOpts(title=f"{year}全国招聘数据"),
            visualmap_opts=VisualMapOpts(
                is_show=True,
                is_piecewise=True,
                pieces=pieces
            )
        )
        map_chart.render(output_file)
        self.logger.info(f"热力图已保存至: {output_file}")
    # 从数据库获取对应年份的职位要求数据，返回字符串
    def get_field_from_db(self, data_year):
        connection = self.get_db_connection()
        field_text = ""
        try:
            with connection.cursor() as cursor:
                sql = "SELECT requirements FROM job_listings WHERE data_year = %s"
                cursor.execute(sql, (data_year,))
                results = cursor.fetchall()
                self.logger.info(f"查询 {data_year} 年数据，返回 {len(results)} 条记录")

                # 输出前3条记录的前100个字符
                for i, row in enumerate(results[:3]):
                    if row[0]:
                        self.logger.debug(f"记录 {i + 1}: {row[0][:100]}...")

                for row in results:
                    if row[0]:
                        field_text += row[0] + "\n"

                # 检查最终拼接的文本长度
                self.logger.info(f"{data_year}年职位要求文本总长度: {len(field_text)}")
                if len(field_text) > 0:
                    self.logger.debug(f"职位要求文本前100个字符: {field_text[:100]}...")
                else:
                    self.logger.warning(f"{data_year}年职位要求文本为空")

            return field_text
        except Exception as e:
            self.logger.error(f"查询错误: {e}")
            return ""
        finally:
            if connection:
                connection.close()



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




    # 绘制热力图
    def generate_job_distribution_heatmap(self, data, output_file="job_distribution_heatmap.heatmap"):
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
    # def salary_distribution(self, salaries, year, should_plot_kde=True):
    #      """
    #      生成薪资分布直方图和薪资分布曲线
    #      :param salaries: 薪资数据列表
    #      :param year: 数据年份
    #      :param should_plot_kde: 是否绘制薪资分布曲线
    #      """
    #      # 数据清洗
    #      parsed = [s for s in (self.parse_salary(x) for x in salaries) if s is not None]
    #
    #      # 薪资合理性过滤
    #      valid = [s for s in parsed if 1500 <= s <= 150000]  # 扩展合理范围
    #
    #      if not valid:
    #          print("无有效数据可供可视化")
    #          return
    #
    #      # 动态分箱策略
    #      q95 = np.percentile(valid, 95)
    #      bins = np.linspace(
    #          max(2000, np.percentile(valid, 5)),  # 排除最低5%
    #          min(q95, 100000),  # 排除超过95%的高薪
    #          num=min(20, len(valid) // 10)  # 自适应分箱数量
    #      )
    #
    #      # 可视化设置
    #      plt.figure(figsize=(14, 7))
    #      n, bins, patches = plt.hist(
    #          valid,
    #          bins=bins,
    #          edgecolor='white',
    #          color='#2196F3',
    #          alpha=0.85
    #      )
    #
    #      # 添加薪资分布曲线
    #      if should_plot_kde:
    #          kde = gaussian_kde(valid)
    #          x = np.linspace(bins[0], bins[-1], 500)
    #          plt.plot(x, kde(x) * len(valid) * np.diff(bins)[0],
    #                   color='#FF5722',
    #                   linewidth=2,
    #                   label='分布曲线')
    #
    #      # 高级格式化
    #      ax = plt.gca()
    #      ax.xaxis.set_major_formatter(plt.FuncFormatter(
    #          lambda x, _: f'{x / 10000:.1f}万' if x >= 10000 else f'{int(x)}元'))
    #      plt.xticks(rotation=45)
    #
    #      # 添加统计信息
    #      stats_text = f"""统计摘要（{datetime.now().strftime('%Y-%m-%d')}）:
    #      - 有效样本: {len(valid):,}
    #      - 中位月薪: {np.median(valid):,.0f}元
    #      - 平均月薪: {np.mean(valid):,.0f}元
    #      - 主要区间: {np.percentile(valid, 25):,.0f} - {np.percentile(valid, 75):,.0f}元"""
    #
    #      plt.annotate(stats_text, xy=(0.68, 0.72), xycoords='axes fraction',
    #                   bbox=dict(boxstyle="round", fc="white", alpha=0.9),
    #                   fontsize=10)
    #
    #      plt.title(f"{year}企业薪资分布分析报告", fontsize=16, pad=20)
    #      plt.xlabel('月薪（人民币）', fontsize=12)
    #      plt.ylabel('职位数量', fontsize=12)
    #      # y轴方向添加网格线,透明都为0.3
    #      plt.grid(axis='y', alpha=0.3)
    #      # 用于在当前绘图区域添加图例
    #      plt.legend()
    #      # 代码的作用是自动调整子图参数，保证子图之间以及子图与绘图区域边缘之间有合适的间距，避免出现元素重叠的情况，从而使绘图布局更加紧凑、美观。
    #      plt.tight_layout()
    #      # 保存图片
    #      plt.savefig(f"薪资统计.png", dpi=300)
    #      # plt.show()

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
        plt.savefig(f"result/salary/{year}_salary_distribution.png", dpi=300)
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
        #print(type(data))
        processed_data = self.process_data(data)
        mapped_data = self.map_data(processed_data)
        self.generate_province_recruitment_map(mapped_data, year, f"result/heatmap/{year}.html")
        # 绘制薪资分布图
        salary = self.get_salary_data(year)
        if salary:
            self.plot_salary_distribution(salary, year)
