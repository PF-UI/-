import yaml
from pathlib import Path
import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime
from typing import Dict, List, Any

class ConfigLoader:
    """配置加载器，用于从YAML文件中读取并管理配置"""

    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化配置加载器并读取配置文件

        Args:
            config_path: 配置文件路径，默认值为 'config/config.yaml'
        """
        self.config_path: Path = Path(config_path)
        self.config: Dict[str, Any] = self._load_config()

        # 数据库配置
        self.global_db_config = self.config.get('database', {})  # 全局数据库配置（字典）
        self.module_db_config = self.config.get('data_analyzer', {}).get('database', {})  # 模块级数据库配置（字典）
        self.db_config = {**self.global_db_config, **self.module_db_config}  # 合并后的字典
        # 职位列表
        self.positions: List[str] = self.config.get('positions', [])

        # 日志配置
        self.logging_config: Dict[str, Any] = self.config.get('logging', {})
        self.log_dir: str = self.logging_config.get('log_dir', 'logs')
        self.file_prefix: str = self.logging_config.get('file_prefix', 'analysis')
        self.log_level: int = self.logging_config.get('level', logging.INFO)
        self.console_level: int = self.logging_config.get('console_level', logging.INFO)
        self.log_format: str = self.logging_config.get('format',
                                                   '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # 图片路径配置
        self.images_config: Dict[str, Any] = self.config.get('images', {})

        # 数据文件路径配置
        self.data_files: Dict[str, Any] = self.config.get('data_files', {})

        # 确保日志目录存在
        self._ensure_log_dir_exists()

    def _load_config(self) -> Dict[str, Any]:
        """加载并解析配置文件，包含错误处理"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"警告：配置文件 {self.config_path} 不存在，使用默认配置")
            return {}
        except yaml.YAMLError as e:
            print(f"警告：配置文件解析失败 ({e})，使用默认配置")
            return {}

    def _ensure_log_dir_exists(self) -> None:
        """确保日志目录存在，不存在则创建"""
        os.makedirs(self.log_dir, exist_ok=True)

    def setup_logging(self, logger_name: str = __name__) -> logging.Logger:
        """
        配置日志记录器（支持按日期分割日志文件）

        Args:
            logger_name: 日志记录器名称，默认使用模块名

        Returns:
            配置好的 logging.Logger 实例
        """
        logger = logging.getLogger(logger_name)
        logger.setLevel(self.log_level)  # 设置日志级别

        # 避免重复添加处理器（关键修复点）
        if logger.handlers:
            return logger  # 已有处理器时直接返回

        # 创建按日期分割的文件处理器
        log_file = f"{self.log_dir}/{self.file_prefix}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=7,  # 保留7天日志
            encoding='utf-8'  # 确保日志文件为UTF-8编码
        )
        file_handler.setFormatter(logging.Formatter(self.log_format))
        file_handler.setLevel(self.log_level)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(self.log_format))
        console_handler.setLevel(self.console_level)

        # 添加处理器到日志记录器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def get_data_file(self, year: int or str) -> List[str]:
        """
        获取指定年份的数据文件路径（支持数字和字符串年份）

        Args:
            year: 年份（如 2023 或 "all"）

        Returns:
            对应年份的文件路径列表，不存在时返回空列表
        """
        return self.data_files.get(str(year), [])

    def get_image_path(self, chart_type: str, year: int or str) -> str:
        """
        获取指定类型和年份的图片路径

        Args:
            chart_type: 图表类型（如 "wordcloud" "heatmap"）
            year: 年份（如 2023 或 "all"）

        Returns:
            图片路径字符串，不存在时返回空字符串
        """
        return self.images_config.get(chart_type, {}).get(str(year), "")

    def get_analyzer_config(self, key: str = None) -> Dict[str, Any]:
        """获取数据分析模块的配置（支持键值获取或全部获取）"""
        analyzer_config = self.config.get('data_analyzer', {})
        return analyzer_config[key] if key else analyzer_config