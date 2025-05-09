import streamlit as st
import PyPDF2
import requests
import json
import io
import os
from dotenv import load_dotenv
import html

# Load environment variables
load_dotenv()

class EventAssistantBot:
    def __init__(self, api_key, pdf_path):
        self.api_key = api_key
        self.pdf_text = self.extract_pdf(pdf_path)
        self.system_prompt = """
        You are a friendly Event Information Assistant. Your primary purpose is to answer questions about the event described in the provided context. Follow these guidelines:

1. You can respond to basic greetings like "hi", "hello", or "how are you" in a warm, welcoming manner
2. For event information, only provide details that are present in the context
3. If information is not in the context, politely say "I'm sorry, I don't have that specific information about the event"
4. Keep responses concise but conversational
5. Do not make assumptions beyond what's explicitly stated in the context
6. Always prioritize factual accuracy while maintaining a helpful tone
7. Do not introduce information that isn't in the context
8. If unsure about any information, acknowledge uncertainty rather than guess
9. You may suggest a few general questions users might want to ask about the event
10. Remember to maintain a warm, friendly tone in all interactions
11. You should refer to yourself as "Event Bot"

Remember: While you can be conversational, your primary role is providing accurate information about this specific event based on the context provided.
        """

    def extract_pdf(self, pdf_path):
        """Extract text from the provided PDF file."""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text()
                
                if not text.strip():
                    st.warning("Warning: Extracted PDF text is empty or contains only whitespace.")
                return text
        except Exception as e:
            st.error(f"Error extracting PDF: {str(e)}")
            return ""

    def answer_question(self, query):
        """Use Google Gemini to answer a question based on PDF context."""
        try:
            # Combine the query with the context for the AI
            combined_prompt = f"Event information: {self.pdf_text}\n\nQuestion: {query}\n\nRemember to follow these guidelines:\n{self.system_prompt}"
            
            # Create the payload for Gemini API
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": combined_prompt}
                        ]
                    }
                ]
            }
            
            # Make request to Gemini API
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response_data = response.json()
            
            # Extract the answer from the response
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                # Extract text from the parts in the response
                text_parts = []
                for part in response_data["candidates"][0]["content"]["parts"]:
                    if "text" in part:
                        text_parts.append(part["text"])
                
                return "\n".join(text_parts)
            else:
                if "error" in response_data:
                    return f"Error: {response_data['error']['message']}"
                return "Sorry, I couldn't process your question. Please try again."
                
        except Exception as e:
            return f"An error occurred: {str(e)}"

# Set page configuration
st.set_page_config(
    page_title="Build with AI - Event Bot",
    page_icon="🎫",
    layout="centered"
)

# Create CSS for styling
st.markdown("""
<style>
/* Basic app styling */
body {
    background-color: #0E1117;
    color: white;
}

/* Custom chat container */
.custom-chat-container {
    background-color: white;
    color: black;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    width: 100%;
    min-height: 400px;
    max-height: 700px;
    overflow-y: auto;
}

/* User message bubble */
.user-message {
    background-color: #e6e6e6;
    color: black;
    border-radius: 15px;
    padding: 10px 15px;
    margin: 10px 0;
    text-align: right;
    max-width: 70%;
    margin-left: auto;
}

/* Bot message bubble */
.bot-message {
    background-color: #fcf8ed;
    color: black;
    border-radius: 15px;
    padding: 10px 15px;
    margin: 10px 0;
    text-align: left;
    max-width: 70%;
}

/* Hide streamlit branding */
.reportview-container .main footer {
    visibility: hidden;
}
.stDeployButton {
    display: none;
}

/* Make sure chat container is clean */
.custom-chat-container p {
    margin: 0;
    padding: 0;
    color: black !important;
}

/* Handle chat icons */
.avatar-icon {
    display: inline-block;
    width: 24px;
    height: 24px;
    margin-right: 5px;
    text-align: center;
    line-height: 24px;
    background-color: #F0C05A;
    color: black;
    border-radius: 50%;
    font-weight: bold;
    vertical-align: middle;
}

.user-avatar-icon {
    background-color: #FF4B4B;
    color: white;
}

/* Message container with icon */
.message-container {
    display: flex;
    align-items: flex-start;
    margin-bottom: 15px;
}

.message-container.user {
    flex-direction: row-reverse;
    justify-content: flex-end;
}

/* Fix for user avatar position */
.message-container.user .avatar-icon {
    margin-right: 0;
    margin-left: 5px;
}

/* Force element color overrides */
.custom-chat-container * {
    color: black !important;
}
</style>
""", unsafe_allow_html=True)

# Main app title
st.title("Build with AI - Event Bot")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Get API key from environment variables
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("API key not found in .env file. Please add GEMINI_API_KEY to your .env file.")
    st.stop()

# Initialize the bot
if "bot" not in st.session_state:
    pdf_path = "context.pdf"
    if not os.path.exists(pdf_path):
        st.error(f"PDF file '{pdf_path}' not found in the current directory.")
        st.stop()
    
    with st.spinner("Initializing assistant..."):
        st.session_state.bot = EventAssistantBot(api_key, pdf_path)
    
    # Add welcome message
    if not st.session_state.messages:
        st.session_state.messages.append(
            {"role": "assistant", "content": "Hello! I'm Event bot. How can I help you with information about this event?"}
        )

# Custom Chat UI Implementation - Completely bypassing Streamlit's chat components
# Open a container div for the chat
chat_html = '<div class="custom-chat-container">'

# Add all messages to the custom chat HTML
for message in st.session_state.messages:
    if message["role"] == "user":
        avatar = '<div class="avatar-icon user-avatar-icon">👤</div>'
        chat_html += f'<div class="message-container user">'
        chat_html += avatar
        chat_html += f'<div class="user-message">{html.escape(message["content"])}</div>'
        chat_html += '</div>'
    else:  # assistant
        avatar = '<div class="avatar-icon">🤖</div>'
        chat_html += f'<div class="message-container">'
        chat_html += avatar
        chat_html += f'<div class="bot-message">{html.escape(message["content"])}</div>'
        chat_html += '</div>'

# Close the container div
chat_html += '</div>'

# Render the custom chat container
st.markdown(chat_html, unsafe_allow_html=True)

# Chat input
user_input = st.chat_input("Ask a question about the event...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Generate response
    with st.spinner("Thinking..."):
        response = st.session_state.bot.answer_question(user_input)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Rerun to update the UI
    st.rerun()