import argparse
import http.client
import json
import PyPDF2
import sys

class EventAssistantBot:
    def __init__(self, api_key, pdf_path):
        self.api_key = api_key
        self.pdf_path = pdf_path
        self.pdf_text = self.extract_pdf()
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

    def extract_pdf(self):
        """Extract text from the provided PDF file."""
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text()
                
                if not text.strip():
                    print("Warning: Extracted PDF text is empty or contains only whitespace.")
                return text
        except Exception as e:
            print(f"Error extracting PDF: {str(e)}")
            sys.exit(1)

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

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Event Information Assistant')
    parser.add_argument('--api_key', required=True, help='CyFeature AI API key')
    parser.add_argument('--pdf', required=True, help='Path to the event PDF file')
    args = parser.parse_args()
    
    # Create bot instance
    bot = EventAssistantBot(args.api_key, args.pdf)
    
    print("Event Information Assistant initialized. Ask questions about the event (type 'exit' to quit):")
    
    # Main interaction loop
    while True:
        query = input("\nYour question: ")
        if query.lower() in ['exit', 'quit', 'bye']:
            print("Thank you for using the Event Information Assistant. Goodbye!")
            break
        
        answer = bot.answer_question(query)
        print(f"\nAssistant: {answer}")

if __name__ == "__main__":
    main()