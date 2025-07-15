from tools.request_b import get, post

def GetFieldOrder():
    return get("https://gyytygyy.xidian.edu.cn/Field/GetFieldOrder",{
        'PageNum':1,
        'pageSize':100,
    })