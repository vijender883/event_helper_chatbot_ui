import streamlit as st
import os
import json
import re
import logging
import time
import datetime
from datetime import datetime, timedelta
import http.client
import PyPDF2
import tempfile
import sys
import importlib.util
from main import EventBot, validate_pdf

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(
    page_title="Event Bot",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Apply custom CSS
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: row;
        align-items: flex-start;
    }
    .chat-message.user {
        background-color: #f0f2f6;
    }
    .chat-message.bot {
        background-color: #e1f5fe;
    }
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
    }
    .chat-message .message {
        flex: 1;
    }
    .stTextInput>div>div>input {
        padding: 0.5rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if 'bot' not in st.session_state:
        st.session_state.bot = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'pdf_uploaded' not in st.session_state:
        st.session_state.pdf_uploaded = False
    if 'pdf_path' not in st.session_state:
        st.session_state.pdf_path = None

def display_messages():
    """Display chat messages"""
    for message in st.session_state.messages:
        if message['role'] == 'user':
            with st.container():
                col1, col2 = st.columns([1, 12])
                with col1:
                    st.image("https://api.dicebear.com/6.x/bottts/svg?seed=user", width=40)
                with col2:
                    st.markdown(f"<div class='message'><b>You:</b> {message['content']}</div>", unsafe_allow_html=True)
        else:
            with st.container():
                col1, col2 = st.columns([1, 12])
                with col1:
                    st.image("https://api.dicebear.com/6.x/bottts/svg?seed=bot", width=40)
                with col2:
                    st.markdown(f"<div class='message'><b>Event Bot:</b> {message['content']}</div>", unsafe_allow_html=True)

def save_uploaded_pdf(uploaded_file):
    """Save the uploaded PDF to a temporary file and return the path"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        return tmp_file.name

def main():
    """Main function to run the Streamlit app"""
    initialize_session_state()
    
    # Title and description
    st.title("Event Bot 🤖")
    st.markdown("I'll help you with information about the event, schedule, participants, and more!")

    # Sidebar for PDF upload and API key
    with st.sidebar:
        st.header("Configuration")
        uploaded_file = st.file_uploader("Upload Event PDF", type="pdf")
        api_key = st.text_input("Enter Cyfuture AI API Key", type="password")
        
        if uploaded_file is not None and api_key and st.button("Initialize Bot"):
            with st.spinner("Initializing EventBot..."):
                # Save the uploaded PDF to a temporary file
                pdf_path = save_uploaded_pdf(uploaded_file)
                st.session_state.pdf_path = pdf_path
                
                try:
                    # Validate the PDF
                    validate_pdf(pdf_path)
                    
                    # Initialize the EventBot
                    st.session_state.bot = EventBot(pdf_path, api_key)
                    st.session_state.pdf_uploaded = True
                    
                    # Add welcome message
                    welcome_msg = f"Welcome to the Event Bot for {st.session_state.bot.event_details.get('title', 'the Event')}! How can I help you today?"
                    st.session_state.messages.append({"role": "bot", "content": welcome_msg})
                    
                    st.success("Bot initialized successfully!")
                except Exception as e:
                    st.error(f"Error initializing bot: {str(e)}")
        
        if st.session_state.pdf_uploaded:
            st.success("Bot is ready to use!")
            
            # Show event details
            st.subheader("Event Details")
            if st.session_state.bot:
                st.write(f"**Title:** {st.session_state.bot.event_details.get('title', 'N/A')}")
                st.write(f"**Date:** {st.session_state.bot.event_details.get('date', 'N/A')}")
                if 'location' in st.session_state.bot.event_details and 'full_address' in st.session_state.bot.event_details['location']:
                    st.write(f"**Location:** {st.session_state.bot.event_details['location']['full_address']}")
                
                # Show agenda in an expander
                with st.expander("Event Agenda"):
                    for time, session in st.session_state.bot.event_details.get('agenda', {}).items():
                        st.write(f"**{time}:** {session}")
                
                # Show participants in an expander
                with st.expander(f"Participants ({len(st.session_state.bot.resumes)})"):
                    for resume in st.session_state.bot.resumes:
                        st.write(f"**{resume.get('name', 'Unknown')}**")
                        if 'skills' in resume:
                            st.write(f"Skills: {', '.join(resume.get('skills', []))}")
                        if 'interests' in resume:
                            st.write(f"Interests: {', '.join(resume.get('interests', []))}")
                        st.write("---")
    
    # Display chat messages
    st.subheader("Chat with Event Bot")
    display_messages()
    
    # Chat input
    if st.session_state.pdf_uploaded:
        # Create a form for the chat input to avoid rerunning on each keystroke
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_input("Type your question here...", key="user_input")
            submit_button = st.form_submit_button("Send")
            
            if submit_button and user_input:
                # Add user message to chat
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                # Get bot response
                try:
                    with st.spinner("Thinking..."):
                        bot_response = st.session_state.bot.answer_question(user_input)
                        
                    # Add bot response to chat
                    st.session_state.messages.append({"role": "bot", "content": bot_response})
                    
                    # Use st.rerun() instead of st.experimental_rerun()
                    st.rerun()
                except Exception as e:
                    error_msg = f"I encountered an error while processing your question. Please try again."
                    st.session_state.messages.append({"role": "bot", "content": error_msg})
                    st.error(f"Error: {str(e)}")
                    # Use st.rerun() instead of st.experimental_rerun()
                    st.rerun()
    else:
        st.info("Please upload a PDF and provide an API key to initialize the bot.")
    
    # Cleanup temporary file on app close
    if st.session_state.pdf_path and os.path.exists(st.session_state.pdf_path):
        try:
            import atexit
            atexit.register(lambda path: os.unlink(path) if os.path.exists(path) else None, st.session_state.pdf_path)
        except:
            pass

if __name__ == "__main__":
    main()