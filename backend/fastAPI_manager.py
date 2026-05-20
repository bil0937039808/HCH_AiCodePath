import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

import redis_manager

# import openai_chat
import singleton as sgtn
import Utility
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing_extensions import override


class RequestData(BaseModel):
    # 根據實際需求調整資料欄位型別
    session_id: Optional[str] = None
    test_index: Optional[int] = None
    test_data_queue: Optional[str] = None


# 定義 POST body 的 schema
class JobFilter(BaseModel):
    message: Optional[str] = ""
    session_id: Optional[str] = ""


class FastAPIApp(sgtn.Singleton_C):
    def __init__(self):
        super().__init__()
        # 管理使用者連線： key = user_id, value = websocket
        self.active_connections: Dict[str, WebSocket] = {}

    @property
    def app(self):
        return self.__app

    async def init_FastAPIApp(self, setModuleName: str = __name__):
        self._rds_man_obj = await redis_manager.RedisManager.get_object()
        self.__app = FastAPI(title=setModuleName)
        self.__app.add_middleware(  # 啟用 CORS
            CORSMiddleware,
            allow_origins=["*"],  # 可改成指定網域
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.active_connections: Dict[str, WebSocket] = {}
        self.setup_routes()

    def run(self, set_host: str, set_port: int):
        uvicorn.run(self.__app, host=set_host, port=set_port)

    async def run_async(self, set_host: str, set_port: int):
        # config = uvicorn.Config(app=self.__app, host=set_host, port=set_port, loop="asyncio")
        config = uvicorn.Config(
            app=self.__app,
            host=set_host,
            port=set_port,
            loop="asyncio",
            reload=False,  # 如果是開發環境可以改成 True
            proxy_headers=True,  # 讓 uvicorn 讀取 nginx 傳遞的 Host, X-Forwarded-For
            forwarded_allow_ips="*",
        )
        server = uvicorn.Server(config)
        await server.serve()

    # --- API 端點 ---
    def setup_routes(self):
        @self.__app.post("/api/test_flask/")
        async def test_flask(data: RequestData, request: Request):
            # 直接使用 Pydantic 驗證的資料
            body = data.dict()
            if not body:
                return {"error": "no data in request body"}

            try:
                body["test_data_queue"] = (
                    json.loads(body["test_data_queue"])
                    if body.get("test_data_queue")
                    else None
                )
                indx = body.get("test_index", -1)
                print("test_flask() body:", body, " ; indx:", indx)
                await self._rds_man_obj.test_queue_push(body, indx)
                return {"message": "Vector inserted successfully", "data": body}
            except Exception as e:
                return {"error": str(e)}

        # GET: /api/jobsInit
        @self.__app.get("/api/jobsInit")
        async def jobs_init():
            reData = "Init ok"
            try:
                return {"message": reData}
            except Exception as e:
                return {"error": str(e)}

        # @self.__app.post("/api/jobs_filters")
        # async def get_jobs_with_filters(filters: JobFilter, request: Request):
        #     # 取出篩選條件
        #     print("get_jobs_with_filters()")
        #     message = (filters.message or "").lower()
        #     session_id = filters.session_id or str(uuid.uuid4())
        #     lc_usr_obj=await openai_chat.OpenaiChat.get_object()
        #     get_answer=await lc_usr_obj.ask_LLM(session_id,str(message))
        #     send_data = {
        #         "re_session_id": get_answer["re_session_id"],
        #         "answer": get_answer["answer"]
        #         }
        #     return send_data

        @self.__app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            await websocket.accept()
            self.active_connections[session_id] = websocket
            try:
                while True:
                    # 等待前端傳入 {"ID":str,"message":str}
                    # try:
                    #     data = await websocket.receive_json()
                    #     print(f"收到使用者 {session_id} 的訊息:", data)
                    #     action_map = {
                    #         "chat": self.chat_dispatch,
                    #         "job_skills": self.job_skills_dispatch
                    #     }
                    #     default_action = lambda: print("沒有符合動作:", data["send_name"])
                    #     action = action_map.get(data["send_name"], default_action)
                    #     await action(data)
                    # except Exception as e:
                    #     print("FastAPIApp::websocket_endpoint():",e)

                    data = await websocket.receive_json()
                    print(f"收到使用者 {session_id} 的訊息:", data)
                    action_map = {
                        "chat": self.chat_dispatch,
                        "job_skills": self.job_skills_dispatch,
                    }
                    default_action = lambda: print("沒有符合動作:", data["send_name"])
                    action = action_map.get(data["send_name"], default_action)
                    await action(data)
                    # data = await websocket.receive_json()
                    # print(f"收到使用者 {session_id} 的訊息:", data)
                    # if(data["send_name"]=="chat"):
                    #     message = (data["message"] or "").lower()
                    #     # session_id = data["session_id"] or str(uuid.uuid4())
                    #     data_struct={
                    #         redis_manager.RedisManager.Function_Name: "jobs_filters",
                    #         redis_manager.RedisManager.Function_DataID: data["session_id"],
                    #         "message": str(message)
                    #     }
                    #     await self._rds_man_obj.queue_push(data_struct,redis_manager.RedisKeyInternalMain.MAIN_OpenAI_In.value)
                    #     pass
                    # elif(data["send_name"]=="job_skills"):
                    #     data_struct={
                    #         redis_manager.RedisManager.Function_Name: "job_skills",
                    #         redis_manager.RedisManager.Function_DataID: data["session_id"],
                    #         "select_skills": data["select_skills"]
                    #     }
                    #     await self._rds_man_obj.queue_push(data_struct,redis_manager.RedisKeyInternalMain.MAIN_Postgres_In.value)
                    #     pass

            except WebSocketDisconnect:
                print(f"使用者 {session_id} 斷線")
                del self.active_connections[session_id]

    async def chat_dispatch(self, data: dict) -> None:
        message = (data["message"] or "").lower()
        # session_id = data["session_id"] or str(uuid.uuid4())
        session_id = data["session_id"]  # <-- 取得 session_id
        member_id = data.get("member_id")  # <-- 嘗試取得 member_id

        # --- 新增: 綁定 session_id 與 member_id ---
        if member_id:
            # 我們建立一個 redis key，例如 "session:xxxx:member_id"，值就是 member_id
            # 這裡需要一個簡單的 set key 的功能，我們稍後加到 redis_manager
            # 為了向前推進，我們先假設有這個功能
            try:
                # 這裡的 key 格式很重要，之後會用到
                redis_key = f"session:{session_id}:member_id"
                # --- START: 修正此處 ---
                # 使用新的輔助函式獲取 main DB 的 client
                redis_client = self._rds_man_obj.get_db_client(
                    redis_manager.RedisDataBasesEnum.MAIN
                )
                if redis_client:
                    await redis_client.set(redis_key, member_id, ex=86400)
                    print(f"Redis: 已綁定 session {session_id} 與 member {member_id}")
                else:
                    print("Redis: 獲取 main DB client 失敗，無法綁定。")
                # --- END: 修正 ---
            except Exception as e:
                print(f"寫入 session-member 綁定到 Redis 失敗: {e}")
        # --- 新增結束 ---

        data_struct = {
            redis_manager.RedisManager.Function_Name: "jobs_filters",
            redis_manager.RedisManager.Function_DataID: data["session_id"],
            "message": str(message),
        }
        await self._rds_man_obj.queue_push(
            data_struct, redis_manager.RedisKeyInternalMain.MAIN_OpenAI_In.value
        )

    async def job_skills_dispatch(self, data: dict) -> None:
        data_struct = {
            redis_manager.RedisManager.Function_Name: "job_skills",
            redis_manager.RedisManager.Function_DataID: data["session_id"],
            "select_skills": data["select_skills"],
        }
        await self._rds_man_obj.queue_push(
            data_struct, redis_manager.RedisKeyInternalMain.MAIN_Postgres_In.value
        )

    async def __send_answer(self, user_id: str, answer: str, msg_name: str):
        """後端回傳 {"ID":str,"answer":str}"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(
                {"session_id": user_id, "msg_name": msg_name, "answer": answer}
            )

    async def __send_data(self, user_id: str, items: Any, msg_name: str):
        """後端回傳 [{"AA":"BB"}...]"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(
                {"session_id": user_id, "msg_name": msg_name, "data": items}
            )

    async def jobs_filters_answer_handle(self, get_task: dict) -> None:
        session_id = get_task.get(redis_manager.RedisManager.Function_DataID, None)
        data = get_task.get("answer", "")
        await self.__send_answer(session_id, data, "jobs_filters_answer")

    async def process_job_search_result_handle(self, get_task: dict) -> None:
        session_id = get_task.get(redis_manager.RedisManager.Function_DataID, None)
        data = get_task.get("data", [])
        await self.__send_data(session_id, data, "process_job_search_result")

    async def courses_recommend_handle(self, get_task: dict) -> None:
        session_id = get_task.get(redis_manager.RedisManager.Function_DataID, None)
        data = get_task.get("validated_data", {})
        # print("courses_recommend send:",type(data))
        send_data = Utility.make_json_serializable(data)
        await self.__send_data(session_id, send_data, "courses_recommend")

    @override
    async def work(self, **kwargs):
        action_map = {
            "jobs_filters_answer": self.jobs_filters_answer_handle,
            "process_job_search_result": self.process_job_search_result_handle,
            "courses_recommend": self.courses_recommend_handle,
        }
        await self.work_task(
            redis_manager.RedisKeyInternalMain.MAIN_FastAPI_In.value,
            redis_manager.RedisManager.Function_Name,
            action_map,
        )


if __name__ == "__main__":
    app_instance = FastAPIApp()
    app_instance.run(set_host="0.0.0.0", set_port=8000)