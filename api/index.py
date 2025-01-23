import os
import json
from typing import List
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from openai import OpenAI
from langgraph.pregel.remote import RemoteGraph
from .utils.prompt import ClientMessage, convert_to_openai_messages
from .utils.tools import get_current_weather


from langgraph_sdk import get_client, get_sync_client

load_dotenv()

app = FastAPI()


# Connect via remote graph


class Request(BaseModel):
    messages: List[ClientMessage]


async def stream_text(messages):
    graph_name = "task_maistro" 
    url = "http://localhost:8123"
    graph_name = "task_maistro"
    client = get_client(url=url)
    sync_client = get_sync_client(url=url)
    remote_graph = RemoteGraph(graph_name, client=client, sync_client=sync_client)
    thread = await client.threads.create()
    config = {"configurable": {"user_id": "Test-Double-Texting"}}
    draft_tool_calls = []
    draft_tool_calls_index = -1

    try:
        async for chunk in remote_graph.astream(
            input={"messages": messages}, 
            config=config,
            stream_mode=["messages"]
        ):
            finish_reason = chunk.data[0]['response_metadata'].get('finish_reason')
            if finish_reason == "stop":
                continue


            elif finish_reason == "tool_calls":

                for tool_call in draft_tool_calls:
                    if tool_call["name"]:
                        print("tool_call end")
                        yield 'a:{{"toolCallId":"{id}","toolName":"{name}","args":{args}}}\n'.format(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["arguments"])
                    else:
                        print("tool_call terminate")  
                        yield '9:{{"toolCallId":"{id}","toolName":"{name}","args":{args}}}\n'.format(
                            id=tool_call["id"],
                            name=tool_call["name"],
                            args=tool_call["arguments"])
            # elif chunk.data[0]['tool_call_chunks']:
            #     tool_call_chunks = chunk.data[0]['tool_call_chunks']
            #     if tool_call_chunks:
            #         for tool_call_chunk in tool_call_chunks:
            #             if tool_call_chunk["name"]:
            #                 print("tool_call_chunks start")

            #                 yield 'b:{{"toolCallId":"{id}","toolName":"{name}","args":{args}}}\n'.format(
            #                     id=tool_call_chunk["id"],
            #                     name=tool_call_chunk["name"],
            #                     args=tool_call_chunk["args"],
            #                 )
            #             else:
            #                 print("tool_call_chunks processing")
            #                 yield 'c:{{"toolCallId":"{id}","toolName":"{name}","args":{args}}}\n'.format(
            #                     id=tool_call_chunk["id"],
            #                     name=tool_call_chunk["name"],
            #                     args=tool_call_chunk["args"],
            #                 )
            #     else:
            #         print("tool_call_chunks missing")
            else:
                yield '0:{text}\n'.format(text=json.dumps(chunk.data[0]['content']))

    except Exception as e:
        yield f"data: {str(e)}\n\n"


@app.post("/api/chat")
async def handle_chat_data(request: Request, protocol: str = Query('data')):
    response = StreamingResponse(stream_text(request.messages))
    response.headers['x-vercel-ai-data-stream'] = 'v2'
    return response

