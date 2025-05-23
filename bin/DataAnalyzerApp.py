import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
from PIL import Image, ImageTk
import pymysql
from matplotlib import pyplot as plt
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from scipy.stats import gaussian_kde

from bin.DataAnalyzer import DataAnalyzer






# GUI界面模块
class DataAnalyzerApp(DataAnalyzer):
    def __init__(self, root, config_loader):  # 添加 config_loader 参数
        self.root = root
        self.setup_ui()
        self.current_chart_type = None
        self.config_loader = config_loader  # 保存配置加载器实例
        # 直接访问 config_loader 的 db_config 属性（非方法）
        self.db_config = config_loader.db_config  # 替换原有行
        #获取存储不同类型和年份对应的图片路径
        self.image_paths = self.config_loader.images_config
        #print(self.image_paths)


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
        years = [2022, 2023, 2024, 2025, "2022-2025"]
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
        # 获取当前图表类型对应的年份-路径字典
        chart_type_dict = self.image_paths.get(self.current_chart_type, {})
        #print(chart_type_dict)

        # 尝试获取指定年份的图片路径
        if year == "2022-2025":
            image_path = chart_type_dict.get("2022-2025", "")
        else:
            image_path = chart_type_dict.get(year, "")

        if not image_path:
            self.status_var.set(f"未找到 {year} 年的 {self.current_chart_type} 图表")
            return

        self.display_image(image_path)
        self.status_var.set(f"显示 {year} {self.current_chart_type} 图表")
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
       #ttk.Button(job_stats_frame, text="岗位数量统计", command=self.show_job_count_stats).pack(side=tk.LEFT, padx=5)
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

        self.sample_data = []
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
                self.sample_data.append(job)

        # 清空现有数据并插入新数据
        self.job_tree.delete(*self.job_tree.get_children())
        for data in self.sample_data:
            self.job_tree.insert("", tk.END, values=data)

        self.status_var.set(f"找到 {len(self.sample_data)} 条符合条件的岗位信息")

    def query_job_listings(self,location="", search_keyword="", salary_range="", data_year=2025):
        try:
            # 建立数据库连接
            # 建立数据库连接
            connection = super().get_db_connection()

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

    import statistics

    def show_salary_stats(self):
        """显示薪资统计信息"""
        if not hasattr(self, 'sample_data') or not self.sample_data:
            messagebox.showwarning("提示", "请先执行岗位查询获取数据")
            self.status_var.set("薪资统计失败：无查询数据")
            return

        # 提取薪资数据
        salaries = []
        for job in self.sample_data:
            salary_str = job[2]  # 假设薪资信息在元组的第3个位置
            parsed_salary = super().parse_salary(salary_str)
            if parsed_salary is not None:
                salaries.append(parsed_salary)

        if not salaries:
            messagebox.showwarning("提示", "未找到有效的薪资数据")
            self.status_var.set("薪资统计失败：无有效数据")
            return

        # 创建新窗口
        top = tk.Toplevel(self.root)
        top.title("薪资分布分析")
        top.geometry("900x600")
        top.resizable(True, True)

        # 创建一个容器框架
        frame = ttk.Frame(top)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建图表和统计信息的框架
        chart_frame = ttk.LabelFrame(frame, text="薪资分布图表")
        chart_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP, padx=5, pady=5)

        stats_frame = ttk.LabelFrame(frame, text="薪资统计数据")
        stats_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

        # 生成图表并显示在Tkinter窗口中
        fig = Figure(figsize=(7, 5), dpi=100)
        ax = fig.add_subplot(111)

        # 数据清洗
        parsed = [s for s in salaries if s is not None]

        # 薪资合理性过滤
        valid = [s for s in parsed if 1500 <= s <= 150000]  # 扩展合理范围

        if not valid:
            messagebox.showwarning("提示", "无有效数据可供可视化")
            self.status_var.set("薪资统计失败：无有效数据")
            return

        # 动态分箱策略
        q95 = np.percentile(valid, 95)
        bins = np.linspace(
            max(2000, np.percentile(valid, 5)),  # 排除最低5%
            min(q95, 100000),  # 排除超过95%的高薪
            num=min(20, len(valid) // 10)  # 自适应分箱数量
        )

        # 绘制直方图
        n, bins, patches = ax.hist(
            valid,
            bins=bins,
            edgecolor='white',
            color='#2196F3',
            alpha=0.85
        )

        # 添加薪资分布曲线
        kde = gaussian_kde(valid)
        x = np.linspace(bins[0], bins[-1], 500)
        ax.plot(x, kde(x) * len(valid) * np.diff(bins)[0],
                color='#FF5722',
                linewidth=2,
                label='分布曲线')

        # 格式化x轴为人民币单位
        ax.xaxis.set_major_formatter(plt.FuncFormatter(
            lambda x, _: f'{x / 10000:.1f}万' if x >= 10000 else f'{int(x)}元'))
        plt.xticks(rotation=45)

        # 添加统计信息文本
        stats_text = f"""统计摘要:
        - 有效样本: {len(valid):,}
        - 中位月薪: {np.median(valid):,.0f}元
        - 平均月薪: {np.mean(valid):,.0f}元
        - 主要区间: {np.percentile(valid, 25):,.0f} - {np.percentile(valid, 75):,.0f}元"""

        # 在统计信息框架中显示文本
        stats_label = ttk.Label(stats_frame, text=stats_text, justify=tk.LEFT, font=("微软雅黑", 10))
        stats_label.pack(anchor=tk.W, padx=10, pady=10)

        # 设置图表标题和标签
        ax.set_title("企业薪资分布分析", fontsize=14)
        ax.set_xlabel('月薪（人民币）', fontsize=12)
        ax.set_ylabel('职位数量', fontsize=12)
        ax.grid(axis='y', alpha=0.3)
        ax.legend()

        # 将图表嵌入到Tkinter窗口中
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 添加交互工具栏
        toolbar = NavigationToolbar2Tk(canvas, chart_frame)
        toolbar.update()

        self.status_var.set(f"薪资统计完成，共分析{len(valid)}个岗位")

    def _copy_to_clipboard(self, text):
        """将文本复制到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("成功", "统计数据已复制到剪贴板")

    def export_job_data(self):
        """导出查询结果为CSV文件"""
        if not hasattr(self, 'sample_data') or not self.sample_data:
            messagebox.showwarning("提示", "请先执行岗位查询获取数据")
            self.status_var.set("导出失败：无查询数据")
            return

        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            title="导出岗位数据到CSV"
        )

        if not file_path:
            self.status_var.set("导出操作已取消")
            return

        # 写入CSV文件
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                # 写入表头
                writer.writerow(["职位名称", "公司名称", "薪资范围", "工作地点", "数据年份"])
                # 写入数据行
                for job in self.sample_data:
                    # 假设job元组包含: (职位名称, 公司名称, 薪资范围, 工作地点)
                    # 添加数据年份(假设为2025，可根据实际情况修改)
                    writer.writerow([*job, 2025])

            messagebox.showinfo("成功", f"已成功导出 {len(self.sample_data)} 条岗位数据到:\n{file_path}")
            self.status_var.set(f"数据导出成功: {file_path}")

        except Exception as e:
            messagebox.showerror("导出失败", f"导出数据时发生错误: {str(e)}")
            self.status_var.set(f"导出失败: {str(e)}")
            print(f"CSV导出错误: {e}")

