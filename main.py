import streamlit as st

from bot import bot_response



st.title("Meeting Scheduler")

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"

# Initialize or load chat history
if "messages" not in st.session_state:
    #st.session_state.messages = load_chat_history()
    st.session_state["messages"] = []

# Sidebar with a button to delete chat history
with st.sidebar:
    if st.button("Delete Chat History"):
        st.session_state.messages = []



# Display chat messages
for message in st.session_state.messages:
    avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Main chat interface
if prompt := st.chat_input("How can I help?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)
        
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        # Generate response
        response = bot_response(prompt)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        # Check for end of chat
        if "thank you for connecting" in response.lower():
            # Clear messages
            st.session_state.messages = []  

