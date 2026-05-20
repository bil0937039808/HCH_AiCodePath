import pandas as pd
from decimal import Decimal
import json
from datetime import datetime, date, time
from typing import Any, Dict, List, Set, Tuple, Union
import base64
import re
import ast
def dataframe_to_dict_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    將 DataFrame 轉換為 list[dict]，並將所有 Decimal 類型轉換為 string
    
    Args:
        df: 要轉換的 DataFrame
        
    Returns:
        List[Dict]: 轉換後的字典列表，Decimal 已轉為字串
    """
    def convert_decimal_to_string(value: Any) -> Any:
        """遞迴轉換 Decimal 為 string"""
        if isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, dict):
            return {k: convert_decimal_to_string(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [convert_decimal_to_string(item) for item in value]
        elif pd.isna(value):
            return None
        else:
            return value
    
    # 轉換 DataFrame 為字典列表
    dict_list = df.to_dict('records')
    
    # 轉換所有 Decimal 為 string
    converted_list = []
    for record in dict_list:
        converted_record = {k: convert_decimal_to_string(v) for k, v in record.items()}
        converted_list.append(converted_record)
    
    return converted_list


def dict_list_to_dataframe(dict_list: List[Dict[str, Any]], 
                          decimal_columns: Union[List[str], None] = None,
                          auto_detect_decimal: bool = True) -> pd.DataFrame:
    """
    將 list[dict] 還原為 DataFrame，並將指定欄位的 string 轉換回 Decimal
    
    Args:
        dict_list: 要轉換的字典列表
        decimal_columns: 需要轉換為 Decimal 的欄位名稱列表，若為 None 則自動偵測
        auto_detect_decimal: 是否自動偵測可能的 Decimal 欄位
        
    Returns:
        pd.DataFrame: 還原後的 DataFrame，指定欄位已轉為 Decimal
    """
    def is_decimal_string(value: Any) -> bool:
        """檢查字串是否可以轉換為 Decimal"""
        if not isinstance(value, str):
            return False
        try:
            Decimal(value)
            return True
        except:
            return False
    
    def convert_string_to_decimal(value: Any) -> Any:
        """轉換字串為 Decimal"""
        if isinstance(value, str) and is_decimal_string(value):
            return Decimal(value)
        elif value is None or pd.isna(value):
            return None
        else:
            return value
    
    if not dict_list:
        return pd.DataFrame()
    
    # 建立 DataFrame
    df = pd.DataFrame(dict_list)
    
    # 如果沒有指定 decimal_columns，則自動偵測
    if decimal_columns is None and auto_detect_decimal:
        decimal_columns = []
        for col in df.columns:
            # 檢查該欄位的非空值是否都可以轉換為 Decimal
            non_null_values = df[col].dropna()
            if len(non_null_values) > 0:
                # 檢查前幾個值是否為可轉換的字串
                sample_values = non_null_values.head(min(10, len(non_null_values)))
                if all(is_decimal_string(val) for val in sample_values):
                    decimal_columns.append(col)
    
    # 轉換指定欄位為 Decimal
    if decimal_columns:
        for col in decimal_columns:
            if col in df.columns:
                df[col] = df[col].apply(convert_string_to_decimal)
    
    return df

def set_to_dict(data_set: Set[str]) -> Dict[str, Any]:
    """
    將 set[str] 轉換為 dict 格式，用於 JSON 序列化
    
    Args:
        data_set: 要轉換的字串集合
        
    Returns:
        Dict[str, Any]: 包含集合資料的字典，格式為 {"__type__": "set", "__data__": [...]}
    """
    return {
        "__type__": "set",
        "__data__": list(data_set)
    }


def dict_to_set(data_dict: Dict[str, Any]) -> Set[str]:
    """
    將字典還原為 set[str]
    
    Args:
        data_dict: 包含集合資料的字典
        
    Returns:
        Set[str]: 還原後的字串集合
        
    Raises:
        ValueError: 當字典格式不正確時
    """
    if not isinstance(data_dict, dict):
        print("輸入必須是字典類型")
    
    if data_dict.get("__type__") != "set":
        print("字典格式不正確，缺少 '__type__': 'set'")
    
    if "__data__" not in data_dict:
        print("字典格式不正確，缺少 '__data__' 欄位")
    
    data_list = data_dict["__data__"]
    if not isinstance(data_list, list):
        print("'__data__' 必須是列表類型")
    
    return set(data_list)

def make_json_serializable(data: Any) -> Any:
    """
    將複雜結構的資料轉換為 JSON 可序列化的格式
    支援 Decimal, set, datetime, pandas DataFrame, bytes 等類型
    
    Args:
        data: 要轉換的資料
        
    Returns:
        Any: JSON 可序列化的資料
    """
    
    if data is None:
        return None
    
    # 處理 Decimal 類型
    elif isinstance(data, Decimal):
        return {
            "__type__": "decimal",
            "__value__": str(data)
        }
    
    # 處理 set 類型
    elif isinstance(data, set):
        return {
            "__type__": "set",
            "__value__": list(data)
        }
    
    # 處理 datetime 類型
    elif isinstance(data, datetime):
        return {
            "__type__": "datetime",
            "__value__": data.isoformat()
        }
    
    # 處理 date 類型
    elif isinstance(data, date):
        return {
            "__type__": "date",
            "__value__": data.isoformat()
        }
    
    # 處理 time 類型
    elif isinstance(data, time):
        return {
            "__type__": "time",
            "__value__": data.isoformat()
        }
    
    # 處理 pandas DataFrame
    elif isinstance(data, pd.DataFrame):
        return {
            "__type__": "dataframe",
            "__value__": {
                "data": make_json_serializable(data.to_dict('records')),
                "columns": list(data.columns),
                "index": list(data.index)
            }
        }
    
    # 處理 pandas Series
    elif isinstance(data, pd.Series):
        return {
            "__type__": "series",
            "__value__": {
                "data": make_json_serializable(data.to_dict()),
                "name": data.name,
                "index": list(data.index)
            }
        }
    
    # 處理 bytes 類型
    elif isinstance(data, bytes):
        return {
            "__type__": "bytes",
            "__value__": base64.b64encode(data).decode('utf-8')
        }
    
    # 處理 tuple 類型
    elif isinstance(data, tuple):
        return {
            "__type__": "tuple",
            "__value__": [make_json_serializable(item) for item in data]
        }
    
    # 處理 frozenset 類型
    elif isinstance(data, frozenset):
        return {
            "__type__": "frozenset",
            "__value__": list(data)
        }
    
    # 處理 complex 複數類型
    elif isinstance(data, complex):
        return {
            "__type__": "complex",
            "__value__": {"real": data.real, "imag": data.imag}
        }
    
    # 處理字典類型
    elif isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # 處理非字串 key 的情況
            if not isinstance(key, (str, int, float, bool, type(None))):
                # 將非標準 key 轉換為字串
                str_key = f"__key__{type(key).__name__}:{str(key)}"
                result[str_key] = {
                    "__type__": "non_string_key",
                    "__key_type__": type(key).__name__,
                    "__key_value__": make_json_serializable(key),
                    "__value__": make_json_serializable(value)
                }
            else:
                result[key] = make_json_serializable(value)
        return result
    
    # 處理列表類型
    elif isinstance(data, list):
        return [make_json_serializable(item) for item in data]
    
    # 處理 pandas 的 NaN 和 NaT
    elif pd.isna(data):
        return {
            "__type__": "pandas_na",
            "__value__": None
        }
    
    # 基本類型（str, int, float, bool）直接返回
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data
    
    # 其他未知類型，嘗試轉換為字串
    else:
        return {
            "__type__": "unknown",
            "__class__": type(data).__name__,
            "__value__": str(data)
        }
    
def fix_unterminated_list(s):
    """
    檢查字串是否為未閉合的列表表示，並在必要時修補。
    """
    if isinstance(s, str):
        s = s.strip()
        # 檢查字串是否以 ']' 結尾
        if not s.endswith(']'):
            # 檢查字串是否以 '[' 開頭，並且包含至少一個單引號或雙引號
            if s.startswith('[') and re.search(r"['\"]", s):
                # 簡單地加上閉合的 ']'
                return s + ']'
    return s

def clean_skill_list_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    處理 DataFrame 中某一欄的技能清單字串，轉成乾淨的 list[str]。

    參數:
        df  : 輸入的 DataFrame
        col : 欄位名稱 (該欄位內部是字串, 內容為 ['Python','JavaScript', ...])

    回傳:
        新的 DataFrame，欄位 col 已轉為 list[str]，並新增一欄 col+'_suspect'
        用來標記是否包含疑似不完整/異常的技能。
    """
    def process_cell(cell: str) -> tuple[list[str], bool]:
        skills: list[str] = []
        suspect = False

        if not isinstance(cell, str):
            return skills, True  # 非字串當作異常

        try:
            # 嘗試用 ast.literal_eval 轉換成 list
            parsed = ast.literal_eval(cell)
            if isinstance(parsed, list):
                skills = [str(s).strip() for s in parsed if str(s).strip()]
            else:
                skills = [str(parsed).strip()]
        except Exception:
            # 如果字串不完整，退而求其次用逗號拆
            skills = [s.strip(" '") for s in cell.strip("[]").split(",") if s.strip()]
            suspect = True

        # 去重複
        skills = list(dict.fromkeys(skills))

        # 標記異常條件：太短、疑似截斷
        for s in skills:
            if len(s) < 3 or s.endswith((" ", "-", ".")):
                suspect = True

        return skills, suspect

    # 套用到 DataFrame 欄位
    results = df[col].apply(process_cell)
    df[col] = results.apply(lambda x: x[0])
    df[col + "_suspect"] = results.apply(lambda x: x[1])
    return df