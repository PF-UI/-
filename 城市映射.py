import pandas as pd
import pymysql

# 数据库连接配置
connection = pymysql.connect(
    host='127.0.0.1',
    user='visitor',
    password='pf123456',
    database='zpsj',
    charset='utf8mb4'
)

# 手动定义未正确映射的数据到省份的映射关系
unmapped_mapping = {
    "潜江": "湖北省",
    "海宁": "浙江省",
    "襄阳": "湖北省",
    "澄迈": "海南省",
    "昆山": "江苏省",
    "仙桃": "湖北省",
    "张家港": "江苏省",
    "常熟": "江苏省",
    "太仓": "江苏省",
    "呼和": "内蒙古自治区",
    "哈尔": "黑龙江省",
    "石家": "河北省",
    "连云": "江苏省",
    "乌鲁": "新疆维吾尔自治区",
    "驻马": "河南省",
    "乐东黎族自治县": "海南省",
    "陵水黎族自治县": "海南省",
    "马鞍": "安徽省",
    "秦皇": "河北省",
    "齐齐": "黑龙江省",
    "昌吉": "新疆维吾尔自治区",
    "文昌": "海南省",
    "日喀则": "西藏自治区",
    "阿克苏": "新疆维吾尔自治区",
    "西双版纳": "云南省",
    "阿勒泰": "新疆维吾尔自治区",
    "巴音郭楞": "新疆维吾尔自治区",
    "济源市": "河南省",
    "大理": "云南省",
    "万宁": "海南省",
    "哈密": "新疆维吾尔自治区",
    "五家渠市": "新疆维吾尔自治区",
    "阿坝": "四川省",
    "林芝": "西藏自治区",
    "琼海": "海南省",
    "儋州": "海南省",
    "和田": "新疆维吾尔自治区",
    "凉山": "四川省",
    "黔南": "贵州省",
    "黔东南": "贵州省",
    "海西": "青海省",
    "德宏": "云南省",
    "延边": "吉林省",
    "怒江": "云南省",
    "克孜勒苏柯尔克孜": "新疆维吾尔自治区",
    "甘孜": "四川省",
    "鄂尔": "内蒙古自治区",
    "昌都": "西藏自治区",
    "红河": "云南省",
    "平顶": "河南省",
    "临夏": "甘肃省",
    "克拉": "新疆维吾尔自治区",
    "昌吉": "新疆维吾尔自治区",
    "昌江": "海南省",
    "毕节": "贵州省",
    "琼海": "海南省",
    "儋州": "海南省",
    "和田": "新疆维吾尔自治区",
    "阿克苏": "新疆维吾尔自治区",
    "阿勒泰": "新疆维吾尔自治区",
    "巴音郭楞": "新疆维吾尔自治区",
    "大理": "云南省",
    "万宁": "海南省",
    "哈密": "新疆维吾尔自治区",
    "五家渠市": "新疆维吾尔自治区",
    "阿坝": "四川省",
    "林芝": "西藏自治区"
}

try:
    with connection.cursor() as cursor:
        # 创建 city_mapping 表
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS city_mapping (
            short_name VARCHAR(255) NOT NULL,
            full_name VARCHAR(255) NOT NULL
        )
        """
        cursor.execute(create_table_sql)

        # 使用 pandas 读取 CSV 文件
        df = pd.read_csv('城市映射.csv', header=None)

        # 处理数据，假设数据格式为 'short_name: full_name'
        df[['short_name', 'full_name']] = df[0].str.split(':', expand=True)
        df['short_name'] = df['short_name'].str.strip()
        df['full_name'] = df['full_name'].str.strip()

        # 去除市
        df['short_name'] = df['short_name'].str.replace('市', '')

        # 额外添加数据
        extra_data = [(key, value) for key, value in unmapped_mapping.items()]
        for short_name, full_name in extra_data:
            insert_sql = "INSERT INTO city_mapping (short_name, full_name) VALUES (%s, %s)"
            cursor.execute(insert_sql, (short_name, full_name))

        # 逐行插入数据到数据库
        for index, row in df.iterrows():
            insert_sql = "INSERT INTO city_mapping (short_name, full_name) VALUES (%s, %s)"
            cursor.execute(insert_sql, (row['short_name'], row['full_name']))

    # 提交事务
    connection.commit()
    print("表创建成功，数据插入成功")
except FileNotFoundError:
    print("CSV 文件未找到")
except Exception as e:
    print(f"发生错误: {e}")
    connection.rollback()
finally:
    # 关闭连接
    connection.close()
