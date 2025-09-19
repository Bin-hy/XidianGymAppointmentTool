from tools.request_b import get, post
import json

"""
羽毛球相关API
"""

def GetVune():
    return get("https://gyytygyy.xidian.edu.cn/Field/GetVenue",
               {
                   "VenueNo": "02",
               })


def GetFieldType():
    return get("https://gyytygyy.xidian.edu.cn/Field/GetFieldType",
               {
                   "FieldTypeNo": "021",
               })


def GetWeek():
    return get("https://gyytygyy.xidian.edu.cn/Field/GetWeek",
               {
                   "VenueNo": "02",
                   "FieldTypeNo": "021",
               })

def GetOrderInfo():
    return get("https://gyytygyy.xidian.edu.cn/Field/GetOrderInfo",
               {
                   "VenueNo": "02",
               })


def CheckUserStatus():
    """
    :return: 返回一个整形 1 | 0
    """
    return get("https://gyytygyy.xidian.edu.cn/User/CheckUserStatus",
               {
               })

def OrderField2():
    checkdata = [
        {
            "FieldNo":"YMQ001",
            "FieldTypeNo":"021",
            "FieldName":"羽毛球1",
            "BeginTime":"14:00",
            "EndTime":"15:00",
            "Price":"0.00"
        }
    ]
    checkdata_json_str = json.dumps(checkdata, ensure_ascii=False)  # ensure_ascii=False 确保中文不被转义
    dateadd = 2
    VenueNo = "02"

    return get("https://gyytygyy.xidian.edu.cn/Field/OrderField",
               {
                   "checkdata": checkdata_json_str,
                   "dateadd": dateadd,
                   "VenueNo": VenueNo,
               })


def OrderField(checkdata: list, dateadd: int, VenueNo: str):
    """
    生成订单。
    :param checkdata: 包含场地信息的列表，例如 [{"FieldNo":"YMQ001", "FieldTypeNo":"021", "FieldName":"羽毛球1", "BeginTime":"14:00", "EndTime":"15:00", "Price":"0.00"}]
    [{'BeginTime': '17:00', 'Count': '2', 'DateBeginTime': '2025-07-21 17:00:00', 'DateEndTime': '2025-07-21 18:00:00', 'EndTime': '18:00', 'FieldName': '羽毛球场1号', 'FieldNo': 'GYMQ001', 'FieldState': '0', 'FieldTypeNo': '021', 'FinalPrice': '0.00', 'IsHalfHour': '0', 'MembeName': '已过期', 'ShowWidth': '100', 'TimePeriod': '1', 'TimeStatus': '1'}]
    :param dateadd: 当前日期偏移量 0表示当天 1表示下一天
    :param VenueNo: 场馆编号，例如 "02"
    :return: API响应JSON数据
    [{'FieldNo': 'GYMQ001', 'FieldTypeNo': '021', 'FieldName': '羽毛球场1号', 'BeginTime': '17:00', 'EndTime': '18:00', 'Price': '0.00'}], dateadd=1, VenueNo=02
    """
    checkdata_json_str = json.dumps(checkdata, ensure_ascii=False)

    # 确认这是一个GET请求，参数通过URL传递
    return get("https://gyytygyy.xidian.edu.cn/Field/OrderField",
               params={
                   "checkdata": checkdata_json_str,
                   "dateadd": dateadd,
                   "VenueNo": VenueNo,
               })

def GetVenueStateNew(dateadd: int = 0, TimePeriod: int = 0):
    """
    获取具体场地信息。
    :param dateadd: 当前日期偏移量 0表示当天 1表示下一天
    :param TimePeriod: 0 上午 1 下午 2 晚上
    :return: API响应JSON数据
    """
    # 假设 FieldTypeNo="021" 是羽毛球场的类型编号
    return get("https://gyytygyy.xidian.edu.cn/Field/GetVenueStateNew",
               params={
                   "dateadd": dateadd,
                   "VenueNo": "02", # 广州研究院场馆编号是02
                   "TimePeriod": TimePeriod,
                   "FieldTypeNo": "021", # 羽毛球场地编号
               })
