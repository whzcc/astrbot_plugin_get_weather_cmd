from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os,datetime
import json
import requests
from astrbot.api.event.filter import event_message_type
import numpy as np
from datetime import datetime
import json
from astrbot.api.all import *
from astrbot.api.event import filter, AstrMessageEvent


import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from scipy.interpolate import make_interp_spline
from PIL import Image as ImageW

@register("astrbot_plugin_get_weather_cmd", "whzc", "获取12小时的天气并生成一张图片", "1.1.0", "repo url")

class Main(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        # 加载配置文件
        self.config = config
        
        # 初始化实例变量
        self.qweather_api_key = self.config.get("qweather_api_key", "")
        self.history_access = bool(self.config.get("history_access", False))
        
    @filter.command("天气")
    async def get_weather(self, event: AstrMessageEvent, msg: str):
        msg = event.get_message_str()
        if not msg:
            yield event.plain_result("请输入正确的指令，如“/天气 深圳”")
            return
        
        def get_weather_hourly(msg,max_terms: int = 12):
            # if location_name == "无":
            #     if self.history_access:
            #         logger.warning("用户输入的消息中没有找到地区名，正在在历史聊天中寻找")
            #         user_input = str("")    # 未完工
            #         completion = client.chat.completions.create(
            #         model="qwen-turbo",
            #         messages=[
            #             {'role': 'system', 'content': '0.输入的内容是一个列表，你需要根据用户最新的输入（列表后面的项）来判断用户输入的地区，具体要求如下。\n1.你需要提取用户输入中的地区名，只需要回复地区名，不要回复其他内容。\n2.只需要回复到“区”的级别。例如，用户说“你好，广州的天气怎么样”，你就要回复“广州”；用户说“广州白云区东风西路的天气怎么样”，你就要回复“广州白云区”而不是“广州白云区东风西路”\n3.如果用户询问了某个景区的名字，请结合你的经验猜测它应该在哪个地方，如用户说“中央大街”，你就回复“哈尔滨道里区”，如果你不知道，直接回复景区名字即可\n4.没有则回复“无”'},
            #             {'role': 'user', 'content': user_input}],
            #         )
            #         location_name = json.loads(completion.model_dump_json())["choices"][0]["message"]["content"]
            #         if location_name == "无":
            #             return
            #     else:
            #         logger.warning("用户输入的消息中没有找到地区名，正在在历史聊天中寻找")
            #         return
                            
            # 城市搜索
            url = "https://geoapi.qweather.com/v2/city/lookup"
            headers = {
                "X-QW-Api-Key": self.qweather_api_key,
                "Accept-Encoding": "gzip, deflate, br",  # 声明支持压缩
            }
            params = {
                "type": "scenic",
                "location": msg
            }

            response = requests.get(
                url,
                headers=headers,
                params=params
            )

            if response.status_code == 200:
                country = response.json()["location"][0]["country"]
                adm1 = response.json()["location"][0]["adm1"]
                adm2 = response.json()["location"][0]["adm2"]
                name = response.json()["location"][0]["name"]
                location_id = response.json()["location"][0]["id"]
                if country == "中国":   # 中国内地
                    if adm2 == name:    # 精确到中国的“市”的情况
                        location = adm1 + adm2 + "市"
                    else:
                        location = adm1 + adm2 + "市" + name + "区"
                else:   # 其他国家或地区
                    if country == adm1:
                        location = country
                    if adm1 == adm2:
                        location = country + " " + adm1
                    if adm2 == name:
                        location = country + " " + adm1 + " " + adm2
                    else:
                        location = country + " " + adm1 + " " + adm2 + " " + name
            else:
                return

            if max_terms <= 24:
                url = "https://devapi.qweather.com/v7/weather/24h"
            elif max_terms <= 72:
                url = "https://devapi.qweather.com/v7/weather/72h"
            elif max_terms <= 168:
                url = "https://devapi.qweather.com/v7/weather/168h"
            headers = {
                "Accept-Encoding": "gzip, deflate, br",  # 声明支持压缩
            }
            params = {
                "key": self.qweather_api_key,
                "location": location_id
            }

            response = requests.get(
                url,
                headers=headers,
                params=params
            )

            if response.status_code == 200:
                return {"location": location, "hourly": response.json()["hourly"][:max_terms]}
            else:
                return

        # 生成图片
        # ======================
        # 数据解析与预处理
        # ======================
        # 理论上支持任何时长的数据，请修改创建画布的比例来获得更好的效果

        data = get_weather_hourly(msg,max_terms=12)
        if not data:
            return
        else:
            # 提取关键数据
            hours = [datetime.fromisoformat(item['fxTime']).strftime('%H:%M') for item in data['hourly']]
            temps = [float(item['temp']) for item in data['hourly']]
            weather_texts = [item['text'] for item in data['hourly']]
            location = data['location']

            # ======================
            # 温度曲线平滑处理
            # ======================
            x = np.arange(len(temps))  # 创建时间索引序列
            y = np.array(temps)

            # 使用三次样条插值生成300个插值点
            x_new = np.linspace(x.min(), x.max(), 300)
            spl = make_interp_spline(x, y, k=3)
            y_smooth = spl(x_new)

            # ======================
            # 可视化配置
            # ======================
            plugin_dir = os.path.dirname(os.path.abspath(__file__))  # 获取当前文件所在目录
            # 中文字体配置
            font_path = os.path.join(plugin_dir, "SourceHanSansCN-Regular.otf")
            prop = fm.FontProperties(fname=font_path, size=12)

            # 创建画布
            fig, ax = plt.subplots(figsize=(16, 9), facecolor='#F5F5F5')

            # ======================
            # 主图表绘制
            # ======================
            # 绘制平滑温度曲线
            ax.plot(x_new, y_smooth, color='#E74C3C', linewidth=2, zorder=10, 
                    label='温度变化曲线')

            # 配置坐标轴
            ax.set_xticks(x)
            ax.set_xticklabels(hours, fontproperties=prop)
            ax.set_xlabel('时间', fontproperties=prop, fontsize=14)
            ax.set_ylabel('温度 (°C)', fontproperties=prop, fontsize=14)
            ax.set_title(f'{location}在未来 12 小时的天气   ', 
                        fontproperties=prop, fontsize=20, pad=10)

            # 网格样式
            ax.grid(True, linestyle='--', alpha=0.6)

            # ======================
            # 天气图标集成
            # ======================
            # 天气图标映射字典
            weather_icons = {
                '晴': os.path.join(plugin_dir, "icons", "sunny.png"),
                '雨': os.path.join(plugin_dir, "icons", "rainy.png"),
                '大雨': os.path.join(plugin_dir, "icons", "rainy.png"),
                '小雨': os.path.join(plugin_dir, "icons", "rainy.png"),
                '中雨': os.path.join(plugin_dir, "icons", "rainy.png"),
                '多云': os.path.join(plugin_dir, "icons", "partly_cloudy.png"),
                '局部多云': os.path.join(plugin_dir, "icons", "partly_cloudy.png"),
                '大部多云': os.path.join(plugin_dir, "icons", "partly_cloudy.png"),
                '雪': os.path.join(plugin_dir, "icons", "snowy.png"),
                '大雪': os.path.join(plugin_dir, "icons", "snowy.png"),
                '小雪': os.path.join(plugin_dir, "icons", "snowy.png"),
                '中雪': os.path.join(plugin_dir, "icons", "snowy.png"),
                '阴': os.path.join(plugin_dir, "icons", "cloudy.png"),
                '风': os.path.join(plugin_dir, "icons", "windy.png"),
                '大风': os.path.join(plugin_dir, "icons", "windy.png"),
                '雾': os.path.join(plugin_dir, "icons", "foggy.png"),
                '大雾': os.path.join(plugin_dir, "icons", "foggy.png"),
            }

            def load_weather_icon(text):
                """加载天气图标并适配大小"""
                icon_path = weather_icons.get(text, os.path.join(plugin_dir, plugin_dir ,"not_supported.png"))
                img = plt.imread(icon_path)
                return OffsetImage(img, zoom=0.2)  # 调整图标显示比例

            # 添加图标注释
            # 新增代码段：沿曲线定位图标
            for xi, yi, text in zip(x, temps, weather_texts):  # 直接使用原始温度数据
                imagebox = load_weather_icon(text)
                
                # 动态偏移计算（占温度范围的15%）
                y_offset = (max(temps)-min(temps)) * 0.15
                offset_sign = 1 if yi > np.median(temps) else -1
                
                ab = AnnotationBbox(
                    imagebox,
                    (xi, yi),  # 绑定原始数据坐标[8](@ref)
                    xycoords='data',
                    xybox=(0, y_offset * offset_sign),  # 垂直偏移
                    boxcoords="offset points",
                    box_alignment=(0.5, 0.5),
                    frameon=False,
                    zorder=30  # 确保顶层显示[3](@ref)
                )
                ax.add_artist(ab)

            # ======================
            # 增强可视化效果
            # ======================
            # 添加温度标注
            for xi, yi in zip(x, y):
                ax.text(xi, yi+0.3, f'{yi}°C', 
                    ha='center', va='bottom',
                    fontproperties=prop,
                    color='#2C3E50',
                    fontsize=16,
                    zorder = 30)

            # 调整图表边距
            plt.subplots_adjust(bottom=0.15)
            
            # 保存图像
            session_id = event.unified_msg_origin.replace(":","")   # 获取session_id并删掉文件系统不兼容的符号 
            img_path_png = os.path.join(plugin_dir, f"{session_id}_weather.png")
            img_path_jpg = os.path.join(plugin_dir, f"{session_id}_weather.jpg")
            plt.savefig(img_path_png, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"astrbot_plugin_get_weather 已生成“{location}”的天气图片。")
            logger.info(f"这是天气情况：{weather_texts}")

            im = ImageW.open(img_path_png)
            im = im.convert('RGB')
            im.save(img_path_jpg, quality=95)
            chain = [
                Plain(f"这是{location}在12小时内的天气。"),
                Image.fromFileSystem(img_path_jpg),
            ]

            yield event.chain_result(chain)

            os.remove(img_path_png)
            os.remove(img_path_jpg)
