import streamlit as st
import PyPDF2
import http.client
import json
import io
import os

class EventAssistantBot:
    def __init__(self, api_key, pdf_file):
        self.api_key = api_key
        self.pdf_text = self.extract_pdf(pdf_file)
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

Remember: While you can be conversational, your primary role is providing accurate information about this specific event based on the context provided.
        """

    def extract_pdf(self, pdf_file):
        """Extract text from the provided PDF file."""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
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
        """Use CyFeature AI to answer a question based on PDF context."""
        try:
            # Combine the query with the context for the AI
            combined_prompt = f"Event information: {self.pdf_text}\n\nQuestion: {query}"
            
            # Connect to CyFeature AI API
            conn = http.client.HTTPSConnection("api.cyfuture.ai")
            
            payload = {
                "model": "llama-8b",
                "messages": [
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": combined_prompt
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.3,
                "stream": False
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            # Send request
            conn.request("POST", "/v1/chat/completions", json.dumps(payload), headers)
            
            # Get response
            response = conn.getresponse()
            response_data = json.loads(response.read().decode())
            
            # Extract the answer from the response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"]
            else:
                return "Sorry, I couldn't process your question. Please try again."
                
        except Exception as e:
            return f"An error occurred: {str(e)}"

# Set page configuration
st.set_page_config(
    page_title="Event Assistant",
    page_icon="🎫",
    layout="centered"
)

# Add CSS for styling
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
    }
    .chat-message.user {
        background-color: #f0f2f6;
    }
    .chat-message.bot {
        background-color: #e6f3ff;
    }
    .chat-message .content {
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# Main app title
st.title("📝 Event Information Assistant")
st.markdown("Upload an event PDF and ask questions about it!")

# Sidebar for API key and file upload
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Enter CyFeature AI API Key", type="password")
    uploaded_file = st.file_uploader("Upload Event PDF", type="pdf")
    
    st.markdown("---")
    st.markdown("### Example Questions")
    st.markdown("""
    - When is the event scheduled?
    - Where is the event located?
    - Who are the speakers?
    - What's on the agenda?
    - Are there any registration fees?
    """)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize bot when PDF is uploaded
if uploaded_file is not None and api_key:
    # Create a copy of the file in memory
    pdf_bytes = io.BytesIO(uploaded_file.getvalue())
    
    # Initialize the bot if not already done
    if "bot" not in st.session_state:
        with st.spinner("Processing PDF..."):
            st.session_state.bot = EventAssistantBot(api_key, pdf_bytes)
        st.success(f"PDF '{uploaded_file.name}' loaded successfully!")
        
        # Add welcome message
        if not st.session_state.messages:
            st.session_state.messages.append(
                {"role": "assistant", "content": "Hello! I'm your Event Information Assistant. How can I help you with information about this event?"}
            )

# Display requirements if not met
if not api_key:
    st.warning("Please enter your CyFeature AI API key in the sidebar.")
if not uploaded_file:
    st.warning("Please upload an event PDF file in the sidebar.")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
if uploaded_file is not None and api_key:
    user_input = st.chat_input("Ask a question about the event...")
    
    if user_input:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Display user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.bot.answer_question(user_input)
                st.write(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})