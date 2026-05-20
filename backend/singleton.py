import asyncio
from typing import TypeVar, Type, Any
T = TypeVar("T", bound="Singleton_C")
class Singleton:
    _instances = {}

    def __new__(cls, *args, **kwargs):
        instance = None
        new_flag = kwargs.get("new", False)
        if (new_flag) or (cls not in cls._instances):
            print("new", cls)
            instance = super().__new__(cls)
            cls._instances[cls] = instance
        else:
            instance = cls._instances[cls]
        # 把 kwargs 暫存起來，給 __init__ 用
        instance._init_kwargs = kwargs
        return instance

class Singleton_C:
    _obj = None  
    _lock = asyncio.Lock()  
    @classmethod
    async def get_object(cls: Type[T]) -> T:
        """非同步取得或建立單例"""
        if cls._obj is None:
            async with cls._lock:
                if cls._obj is None:  # double check
                    cls._obj = cls()
                    
        return cls._obj

    def __init__(self):
        self._rds_man_obj=None
        if self.__class__._obj != None :
            print(f"new {self.__class__.__name__} ,{hex(id(self))}")
            raise RuntimeError("Singleton_C:Use get_object() instead")
        
    async def work_task(self, index: int, function_name: str, action_map: dict) -> Any:
        get_task = await self._rds_man_obj.queue_pop(index)
        if not get_task:
            return None
        
        print(self.__class__.__name__, " work():", get_task, type(get_task))
        task_name = get_task.get(function_name)
        print(self.__class__.__name__, " work() name:", task_name)
        
        # 使用傳入的 action_map，並將 get_task 傳給 lambda
        default_action = lambda: print("沒有符合動作:", task_name)
        action = action_map.get(task_name, default_action)
        result=await action(get_task)
        return result
        # 如果 action 需要 get_task 參數
        # if hasattr(action, '__code__') and action.__code__.co_argcount > 0:
        #     await action(get_task)
        # else:
        #     await action()

    async def work(self, **kwargs)-> None:
        pass

    async def work_test(self, **kwargs)-> None:
        pass
