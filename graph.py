# -*- coding: utf-8 -*-
"""Data Analysis Agent.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/14oTVEmsU7OR3Z6kTTZ7n-7VyJ8QdJmEC
"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install -qU langgraph langchain-openai langchain-community pandas matplotlib langchain_experimental


import streamlit as st

import pandas as pd
# from IPython.display import Image, display
from typing import List, Literal, Optional, TypedDict, Annotated
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.utilities import GoogleSerperAPIWrapper


class State(TypedDict):
	messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)

# Configure AzureChatOpenAI
llm = AzureChatOpenAI(
    deployment_name= st.secrets["deployment_name"],  # Your Azure OpenAI deployment name
    api_key=st.secrets["azure_api_key"],  # Your Azure OpenAI API key
    azure_endpoint=st.secrets["endpoint"],
    openai_api_version=st.secrets["api_version"],# API version for Azure OpenAI
    max_tokens=6000,
)

serper_tool = GoogleSerperAPIWrapper(serper_api_key=st.secrets["serper_api_key"])

# Function to create the ToolNode
def create_serper_tool_node(tool):
    """
    Creates a ToolNode for the given tool.

    Args:
        tool (callable): A callable tool function to be executed within the ToolNode.

    Returns:
        ToolNode: A configured ToolNode with the provided tool.
    """
    return ToolNode(tools=[tool])

# Bind tools with AzureChatOpenAI
llm_with_tools = llm.bind_tools([serper_tool.run])

#Check for prompts.
# Create diffrent node for each tasks.
# Ask for questions if clarrification are needed.

def chatbot(state: State):
    system_prompt = {
        "role": "system",
        "content": (
            """
    You are a market research agent tasked with providing detailed and accurate insights about companies and their contexts. Your responsibilities include:

    1. If the user's question is unclear or ambiguous, ask the user for clarification. Ensure you fully understand the query before proceeding.
    2. Once the question is clarified, evaluate if the context provided by the user is sufficient to generate a meaningful answer. If it's not sufficient:
        - Suggest a query to search for additional information using the Serper tool.
        - Use the Serper tool to retrieve the required context.
    3. After retrieving the initial context:
        - If the context is still insufficient, refine the query and use the Serper tool again to gather more information.
        - Repeat this until the context is adequate for a complete answer.
    4. Finally, provide a well-researched, detailed response based on the collected context.
    5. If the question is related to overall inquiry of the company then add these points as well 
        1. **Basic Overview**:
            - **Industry and Sector**: [Industry and sector information]
            - **Headquarters Location**: [Headquarters location]
            - **Year Founded**: [Year founded]

        2. **Size and Scale**:
            - **Number of Employees**: [Number of employees]
            - **Revenue**: [Revenue, if publicly available]
            - **Global Presence**: [Details about international operations, if applicable]

        3. **Funding and Financial Information**:
            - **Total Funds Raised**: [Funds raised for startups/private companies]
            - **Key Investors**: [Notable investors, if applicable]

        4. **Recent Developments**:
            - **Latest News**: [Summarize any recent news like product launches, partnerships, acquisitions, or controversies (Add at max 4-5 points)]

        5. **Products and Services**:
            - [List of offerings by company and their partners (Add at max 4-5 points)]

        6. **References and Links**:
            - For more details, visit:
            - [Company Website](link to official website)
            - [Relevant News Article](link to news article)
            - [Crunchbase Profile](link to Crunchbase profile, if available)
        7. It should call serper tool multiple times to gatter complete information.

    Your responses should follow this structure:
    - If clarification is needed: "Your question is unclear. Can you please provide more details or clarify your query?"
    - If Serper query is required: "QUERY: <suggested_search_query>"
    - If sufficient context is gathered: "ANSWER: <detailed_research_based_answer>"

    Note: For company details, it should call the Serper tool multiple times if necessary to gather complete information. Ensure to use sources like TechCrunch, VentureBeat, news.ycombinator.com, LinkedIn, and Angel.co. While these sources are not 100% real-time, they provide valuable insights.
    If some details are still not available after multiple queries, inform the user: "Some information is not available."
            """
        )
    }
    messages = [system_prompt] + state["messages"]
    
    return {"messages": [llm_with_tools.invoke(messages)]}

graph_builder.add_node("agent", chatbot)


code_execution = create_serper_tool_node(serper_tool.run)

graph_builder.add_node("tools", code_execution)

def route_tools(state: State,):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the end.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"
    return END

graph_builder.add_conditional_edges(
    "agent",
    route_tools,
    {"tools": "tools", END: END},
)

graph_builder.add_edge("tools", "agent")

memory = MemorySaver()
graph_builder.add_edge(START, "agent")

graph = graph_builder.compile(checkpointer=memory)

graph = graph_builder.compile(checkpointer=memory)

# display(Image(graph.get_graph().draw_mermaid_png()))

config = {"configurable": {"thread_id": "1"}}

def stream_graph_updates(user_input: str):
    final_response = ""
    events = graph.stream(
        {"messages": [("user", user_input)]}, config, stream_mode="values"
    )
    for event in events:
        event["messages"][-1].pretty_print()
        if event["messages"][-1].response_metadata and event["messages"][-1].response_metadata['finish_reason'] == 'stop':
            final_response = event["messages"][-1].content
            break
    
    return final_response

# async def stream_graph_updates(user_input: str):
#     final_output = None
    
#     async for event in graph.astream(
#         {"messages": [("user", user_input)]}, config, stream_mode="values"
#     ):
#         print(f"Received event: {event}")  # Debug print
#         final_output = event
    
#     return final_output

# while True:
#     user_input = input("User: ")
#     if user_input.lower() in ["quit", "exit", "q"]:
#         print("Goodbye!")
#         break
#     var = stream_graph_updates(user_input)
#     print(var)

# import asyncio
# result = asyncio.run(stream_graph_updates("Tell me about Ai Planet Company"))
# print(result)


