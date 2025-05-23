import tkinter as tk
from bin.DataAnalyzer import DataAnalyzer
from bin.DataAnalyzerApp import DataAnalyzerApp
from bin.JobDataCollector import JobDataCollector
from bin.DataStorage import DataStorage


class RecruitmentAnalysis:
    """招聘数据分析主程序"""

    def __init__(self, config_loader):
        # 从配置加载器获取配置
        self.config_loader = config_loader
        self.db_config = config_loader.db_config
        self.positions = config_loader.positions

        # 配置日志
        self.logger = config_loader.setup_logging(__name__)
        self.logger.info("招聘数据分析系统初始化完成")

        # 初始化模块
        self.collector = JobDataCollector(output_file='data/jobs_data.jsonl')
        self.storage = DataStorage()
        self.analyzer = DataAnalyzer(config_loader)

    def collect_data(self, refresh=False):
        """收集数据"""
        if refresh:
            self.logger.info(f"开始收集{self.positions}职位数据")
            self.collector.collect_jobs(self.positions)
            self.logger.info("数据收集完成")
        else:
            self.logger.info("使用已有数据，跳过收集步骤")

    def store_data(self, overwrite=False):
        """存储数据到数据库"""
        if overwrite:
            self.logger.info("开始将数据存入数据库")
            self.storage.main()
            self.logger.info("数据存储完成")
        else:
            self.logger.info("跳过数据存储步骤")

    def analyze_data(self, years: range = range(2022, 2026), perform_analysis: bool = True) -> None:
        """分析数据并生成图表

        Args:
            years: 要分析的年份范围
            perform_analysis: 是否执行分析操作
        """
        if not perform_analysis:
            self.logger.info("跳过数据分析步骤")
            return

        self.logger.info(f"开始分析{years}年的数据")

        # 按年份分析
        for year in years:
            self.logger.info(f"处理{year}年数据")
            try:
                self.analyzer.process_year(year)
            except Exception as e:
                self.logger.error(f"{year}年数据处理失败: {str(e)}")

        # 综合分析多年数据
        word_data = ""
        salary_data = []
        city_data = []
        for year in years:
            try:
                field_data = self.analyzer.get_field_from_db(year)
                word_data += field_data
                salarys = self.analyzer.get_salary_data(year)
                salary_data.extend(salarys)
                data = self.analyzer.get_data_from_db(year)
                # print(type(data))
                processed_data = self.analyzer.process_data(data)
                city_data.extend(processed_data)

                # 绘制薪资分布图
            except Exception as e:
                self.logger.error(f"获取{year}年数据失败: {str(e)}")

        # 生成综合图表
        try:
            if word_data:
                words = self.analyzer.perform_word_segmentation(word_data)
                self.analyzer.generate_wordcloud(words, f"2022-2025_wordcloud.png")
            if salary_data:
                self.analyzer.plot_salary_distribution(salary_data, year="2022-2025")
            if city_data:
                self.analyzer.generate_province_recruitment_map(city_data, year, f"result/heatmap/all.html")
            self.logger.info("数据分析完成")
        except Exception as e:
            self.logger.error(f"生成综合图表失败: {str(e)}")

    def run_gui(self):
        """运行图形界面"""
        self.logger.info("启动图形界面")
        root = tk.Tk()
        root.title("招聘数据分析系统")
        app = DataAnalyzerApp(root, config_loader)  # 传入ConfigLoader实例，包含images_config
        root.mainloop()


if __name__ == "__main__":
    # 加载配置
    from bin.ConfigLoader import ConfigLoader

    config_loader = ConfigLoader()

    # 创建分析器实例
    analyzer = RecruitmentAnalysis(config_loader)

    # 控制数据收集和存储的开关
    COLLECT_NEW_DATA = False  # 是否收集新数据
    STORE_DATA = False  # 是否将数据存入数据库
    ANALYZE_DATA = False  # 是否进行数据分析

    # 执行分析流程
    analyzer.collect_data(refresh=COLLECT_NEW_DATA)
    analyzer.store_data(overwrite=STORE_DATA)
    analyzer.analyze_data(perform_analysis=ANALYZE_DATA)

    # 启动图形界面
    analyzer.run_gui()