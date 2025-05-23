
import os
import json
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from google.genai import types
from google import genai
from mcp.client.stdio import stdio_client
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=gemini_api_key)
server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y", "@executeautomation/playwright-mcp-server"
        ],
    )

def clean_schema(schema: dict) -> dict:
    """Recursively remove additionalProperties from schema"""
    if not isinstance(schema, dict):
        return schema
        
    cleaned = {}
    for k, v in schema.items():
        if k == "additionalProperties":
            continue
        if isinstance(v, dict):
            cleaned[k] = clean_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_schema(item) for item in v]
        else:
            cleaned[k] = v
    return cleaned

async def run(prompt: str):
    # prompt = f"""Navigate to website https://webwatch.carvia-test.org/login?redirectURL=%252Fdashboard and click on the Login with Keycloak. In the login page, enter
    #             the username and password as \"Saubhagya.carvia\" and \"password\" respectively and perform login.
    #             If you see listing of monitors then test is successful else test is failed."""
    system = f"""
        You are a UI flow testing agent, You have access to tools used for UI testing.
        You will be given a task for testing a web app.
        DO NOT MENTION OR EXPLAIN THE TASK.
        Once all the tool calls are done return with String "Analysis Done" with your result.
        Ensure you follow below steps to complete the given task.
        - Go through the task given and identify the tool calls that are required.
        - when calling a tool, return the details i.e. what are you doing
        IMPORTANT: If a tool call fails for two consecutive times, then return \"Analysis Done\" with your finding.
        task: {prompt}
    """
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Session initialized.")
                yield f"data: Session initialized.\n\n"

                mcp_tools = await session.list_tools()
                print(f"Available tools: {[tool.name for tool in mcp_tools.tools]}")


                tools = [
                    types.Tool(
                        function_declarations=[
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": clean_schema(tool.inputSchema)
                            }
                        ]
                    )
                    for tool in mcp_tools.tools
                ]
                print(f"Prepared tool schemas: {tools}")

                context = []
                final_context = []

                while True:
                    print("Sending prompt to Gemini model...")
                    try:
                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=system + "\nprevious_tool_calls: " + str(context),
                            config=types.GenerateContentConfig(
                                temperature=0,
                                tools=tools,
                            ),
                        )
                        print(f"Model response: {response}")
                        final_context.append({
                            "model_response": response.to_json_dict(),
                        })

                        # Handle empty candidates case
                        if not response.candidates:
                            print("No candidates in response, retrying...")
                            context.append("Error: Empty response from model")
                            continue

                        part = response.candidates[0].content.parts[0]
                        if part and  part.text:
                            if "Analysis Done" in part.text:
                                print("Received 'Done' signal. Exiting loop.")
                                yield f"data: {part.text} Returning the report now..\n\n"
                                with open("output_1.json", "w") as f:
                                    context.append("Analysis Done")
                                    final_context.append({
                                        "model_response": part.text,
                                    })
                                    f.write(json.dumps(final_context, indent=4))

                                    yield f"data: {json.dumps(final_context)}\n\n"
                                yield "event: close\ndata: \n\n"
                                break
                            else:
                                print(f"Model output: {part.text}")
                                context.append(part.text)
                                final_context.append({
                                    "model_response": part.text,
                                })
                                yield f"data: {part.text}\n\n"

                        # Modified exit condition
                        # if hasattr(part, "text") and "done" in part.text.lower():
                        #     print("Received completion signal. Exiting loop.")
                        #     break

                        # Handle missing function calls more gracefully
                        part = response.candidates[0].content.parts[1] if len(response.candidates[0].content.parts) > 1 else part
                        if not hasattr(part, "function_call") or not part.function_call:
                            print("No function call detected, updating context...")
                            context.append("Error: No function call in response")
                            continue  # Continue instead of breaking

                        tool_name = part.function_call.name
                        args = part.function_call.args
                        
                        print(f"Calling tool: {tool_name} with args: {args}")
                        result = await session.call_tool(tool_name, arguments=args)
                        print(f"Result from tool '{tool_name}': {result}")

                        context.append({
                            "name": tool_name,
                            "args": args,
                            "result": str(result)
                        })
                        final_context.append({
                            "tool_name": tool_name,
                            "args": args,
                            "result": str(result)
                        })

                    except Exception as e:
                        print(f"Error in loop: {str(e)}")
                        context.append(f"Error: {str(e)}")
                        continue 
                print("Closing session...")
                await session.complete(None, {})
                return 
    except Exception as e:
        print(f"Error in run function: {str(e)}")
        yield f"data: Error: {str(e)}\n\n"
        yield "event: close\ndata: \n\n"
    finally:
        print("Session closed.")
        yield "event: close\ndata: \n\n"


app = FastAPI()

class InputData(BaseModel):
    prompt: str

@app.get("/test")
async def test_ui(
        prompt: InputData,
):
    """
    Endpoint to test the UI flow using the agent.
    """
    try:
        return StreamingResponse(run(prompt), media_type="text/event-stream")
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "message": "Server is running."}