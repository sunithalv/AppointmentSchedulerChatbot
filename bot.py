from langchain_groq import ChatGroq
from langchain_core.runnables.history import  RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from agent import create_google_calendar_event,send_email
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder
)
from utils import extract_information
from templates import template_1
import os

system_message_prompt = SystemMessagePromptTemplate.from_template(template_1)
human_template="{query}"
human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt,human_message_prompt,
        MessagesPlaceholder(variable_name="chat_history")])


# Assigning model and tools
llm = ChatGroq(model="llama-3.1-8b-instant",temperature=0.3)

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")

chat_history_chain = ChatMessageHistory()


def bot_response(query):
    """
    Function to handle the conversation flow with the chatbot.
    
    Args:
    - query (str): The user input/query
    
    Returns:
    - response (str): The bot response
    """

    chat_history_chain.add_user_message(query)

    conversation = []
    conversation.append('User: ' + query)

    output = groq_response(query)

    chat_history_chain.add_ai_message(output)

    conversation.append('Bot: ' + output)

    # Extract information
    pattern_name = r'\bFull Name:\s*(.*)'
    pattern_service = r'\bService Type:\s*(.*)'
    pattern_location = r'\bLocation:\s*(.*)'
    pattern_start_time = r'\bStart datetime:\s*(.*)'
    pattern_email = r'\bEmail Address:\s*(.*)'

    name = extract_information(conversation, pattern_name)
    service = extract_information(conversation, pattern_service)
    location = extract_information(conversation, pattern_location)
    start_datetime = extract_information(conversation, pattern_start_time)
    email = extract_information(conversation, pattern_email)
    
    # Check if all information is collected
    if name and service and location and start_datetime and email:

        input_data = {
        'fullname':name,
        'service': service,
        'location': location,
        'start_time': start_datetime,
        'email': email
        }
        meet_link=create_google_calendar_event(input_data)
        input_data['meet_link']=meet_link
        send_email(input_data,llm)
    return output


#Get the llm response
def groq_response(query):
    conversation_chain= chat_prompt| llm
    chain_with_message_history = RunnableWithMessageHistory(
    conversation_chain,
    lambda session_id: chat_history_chain,
    input_messages_key="query",
    history_messages_key="chat_history",
)
    
    response=chain_with_message_history.invoke(
    {"query": query}, {"configurable": {"session_id": chat_history_chain}}
    ).content
    return response    



