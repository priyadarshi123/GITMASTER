from dotenv import load_dotenv
import os

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatMessagePromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langchain.agents import create_openai_tools_agent, AgentExecutor

load_dotenv()

todoist_api_python = os.getenv("TODOIST_API_KEY")
gemini_api_python = os.getenv("GEMINI_API_KEY")

@tool
def add_task():
    """Add a new user task to user task list. Use this when user wants to add or create a task"""
    print("Adding Todo")

tools = [add_task]

print(todoist_api_python, gemini_api_python)

llm = ChatGoogleGenerativeAI(model='gemini-2.5-flash',
                             google_api_key=gemini_api_python,
                             temperature=0.3)



system_prompt = "You are a helpful assistant. You will help user add tasks"
user_input= "Add a task for me"

prompt = ChatPromptTemplate([
    ("system",system_prompt),
    ("user",user_input),
    MessagesPlaceholder("agent_scratchpad")
])

#chain = prompt | llm | StrOutputParser()

agent = create_openai_tools_agent(llm,tools,prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

response = agent_executor.invoke({"input":user_input})

#response = chain.invoke({"input": user_input})

print(response)

