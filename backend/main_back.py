import asyncio
import logging
import os
import subprocess
import time

import fastAPI_manager
import match_course
import milvus_manager
import openai_chat
import pandas as pd
import postgres_manager
import redis_manager
import search_data_procese
from dotenv import load_dotenv

keep_work = True


async def main_work():
    print("main_work() started")
    posgr_man_obj = await postgres_manager.PostgresManager.get_object()
    milvs_man_obj = await milvus_manager.MilvusManager.get_object()
    openAI_obj = await openai_chat.OpenaiChat.get_object()
    srch_data_pc = await search_data_procese.SearchDataProcess.get_object()
    flask_obj = await fastAPI_manager.FastAPIApp.get_object()
    mch_crs_obj = await match_course.MatchCourse.get_object()
    rds_man_obj = await redis_manager.RedisManager.get_object()
    while keep_work:
        tasks = [
            posgr_man_obj.work(),
            milvs_man_obj.work(),
            openAI_obj.work(),
            srch_data_pc.work(),
            flask_obj.work(),
            mch_crs_obj.work(),
        ]
        try:
            # 在這裡捕獲來自子任務的異常
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    print(f"一個任務失敗了: {result}")
        except Exception as e:
            print(f"主程式捕獲到未預期的異常: {e}")
        # await asyncio.sleep(1)
    await milvs_man_obj.close_milvus()
    await posgr_man_obj.close_postgres()
    await rds_man_obj.close_redis()


async def main_work_test():
    print("main_work_test() started")
    posgr_man_obj = await postgres_manager.PostgresManager.get_object()
    milvs_man_obj = await milvus_manager.MilvusManager.get_object()
    openAI_obj = await openai_chat.OpenaiChat.get_object()
    srch_data_pc = await search_data_procese.SearchDataProcess.get_object()
    while keep_work:
        await posgr_man_obj.work_test()
        await milvs_man_obj.work_test()
        await openAI_obj.work_test()
        await srch_data_pc.work_test()
        # await asyncio.sleep(1)
    pass


async def main():
    # cmd_test = subprocess.run(["ls"], capture_output=True, text=True)
    # print(cmd_test.stdout)
    # cmd_test = subprocess.run(["ls", "./config"], capture_output=True, text=True)
    # print(cmd_test.stdout)
    # os.chdir("/home/workspace/AIPE01_G4_Project/backend")
    # print(os.getcwd())
    env_path = "./config/key.env"
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
    else:
        print("指定檔案不存在，無法載入環境變數。")
        return

    if openai_api_key == None:
        print("OpenAI Key(OPENAI_API_KEY)不存在")
        return

    openAI_obj = await openai_chat.OpenaiChat.get_object()
    await openAI_obj.init_OpenaiChat("gpt-4.1", openai_api_key)  # gpt-4.1-nano
    print("OpenAI Chat initialized.")

    rds_man_obj = await redis_manager.RedisManager.get_object()
    await rds_man_obj.connect_redis(host="redis7", port=6379, password="admin")
    print("Redis Manager initialized.")

    posgr_man_obj = await postgres_manager.PostgresManager.get_object()
    await posgr_man_obj.connect_postgres(
        host="Postgres16", port=5432, user="admin", password="admin", dbname="projectdb"
    )
    print("Postgres Manager initialized.")

    mlvs_man_obj = await milvus_manager.MilvusManager.get_object()
    await mlvs_man_obj.connect_milvus(openai_api_key, 5, 3, host="milvus", port="19530")
    print("Milvus Manager initialized.")

    srch_data_pc = await search_data_procese.SearchDataProcess.get_object()
    await srch_data_pc.init_SearchDataProcess()
    print("Search Data Process initialized.")

    mch_crs_obj = await match_course.MatchCourse.get_object()
    await mch_crs_obj.init_MatchCourse(openai_api_key, gemini_api_key)
    print("Match Course initialized.")

    flask_obj = await fastAPI_manager.FastAPIApp.get_object()
    await flask_obj.init_FastAPIApp()
    task_fastAPI = asyncio.create_task(
        flask_obj.run_async(set_host="0.0.0.0", set_port=9100)
    )
    print("FastAPI App initialized.")

    task_main = asyncio.create_task(main_work())
    task_main = asyncio.create_task(main_work_test())  # 在 loop 裡建立任務

    p = f"""記憶體位址:,OpenaiChat={hex(id(openAI_obj))}, RedisManager={hex(id(rds_man_obj))},
     PostgresManager={hex(id(posgr_man_obj))}, MilvusManager={hex(id(mlvs_man_obj))}
     , FastAPIApp={hex(id(flask_obj))}"""
    print(p)
    await task_fastAPI
    await task_main  # 等待任務完成


if __name__ == "__main__":
    # flask_obj=fastAPI_manager.FastAPIApp()
    # flask_obj.run(set_host="0.0.0.0", set_port=9100)
    asyncio.run(main())

    #     #我想要成為AI工程師或資料分析師,請問我該具備那些條件? 我會C++和python並且希望工作在台北,薪資在4萬到5萬左右 我想要可以開發應用LLM的工作
# 我想要成為AI工程師 我會C++和python並且希望工作在新竹市,薪資不要求 想要可以開發應用LLM的工作
# 先依據這些資訊搜尋
#我想成為AI工程師
#我會程式語言、機器學習,地點在新竹市,薪資面議,想要從事AI應用開發