import random
import threading
from queue import Queue
import requests
import time
import json
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
