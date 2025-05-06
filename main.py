#!/usr/bin/env python3
import os
import json
import re
import argparse
import logging
import time
import datetime
from datetime import datetime, timedelta
import http.client
import PyPDF2
import spacy
import nltk
from nltk.tokenize import sent_tokenize
import dateutil.parser

# Download necessary NLTK data
nltk.download('punkt', quiet=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EventBot:
    """Event Bot that answers questions based on event details and participant resumes"""
    
    def __init__(self, pdf_path, api_key):
        """Initialize the bot with PDF path and API key"""
        self.pdf_path = pdf_path
        self.api_key = api_key
        self.event_details = {}
        self.resumes = []
        self.feedback = {}  # To store feedback for different sessions
        self.locations = {}
        
        # Define the prompt to use with the API
        self.prompt = """You are an intelligent Event Bot for the "Build with AI" Workshop in collaboration with Google for Developers. Your purpose is to provide timely, accurate information to participants and enhance their event experience.
### Event Information
- Title: Build with AI – A Workshop in Collaboration with Google for Developers
- Date: May 18, 2025
- Location: ScaleOrange technologies, Masthan Nagar, Kavuri Hills, Madhapur, Hyderabad, Telangana 500081, India
- Target Audience: Developers & Engineers, Tech Professionals, Students & Recent Graduates, Entrepreneurs & Product Managers
### Your Capabilities
1. Event Details: Share information about the agenda, schedule, speakers, and venue
2. Navigation Assistance: Help participants find key locations (washrooms, cafeteria, main hall, etc.)
3. Time Management: Provide updates on session timings, lunch breaks, and event duration
4. Networking Support: Identify participants with similar technical backgrounds for networking
5. Session Recommendations: Suggest relevant sessions based on participants' skills and interests
6. Feedback Collection: Gather feedback on sessions in a conversational manner
### Interaction Guidelines
- Provide concise, accurate responses based solely on available information
- For time-related queries, calculate accurate times based on the current time and event schedule
- Base session recommendations and participant matching on technical skills and interests
- Acknowledge when information is unavailable rather than making assumptions
- Maintain a helpful, friendly, and professional tone
- Respond in a conversational manner while keeping answers brief and informative"""
        
        # Process the PDF to extract event details and resume information
        self.process_pdf()
        
    def extract_text_from_pdf(self):
        """Extract text from a PDF file"""
        text = ""
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {self.pdf_path}: {str(e)}")
            raise
            
    def extract_event_details(self, text):
        """Extract event details from text"""
        event_details = {}
        
        # Extract event title
        title_pattern = re.compile(r'(?:Title|Event):\s*(.*?)(?:\n|$)')
        title_match = title_pattern.search(text)
        if title_match:
            event_details['title'] = title_match.group(1).strip()
        else:
            event_details['title'] = "Build with AI – A Workshop in Collaboration with Google for Developers"
        
        # Extract event date
        date_pattern = re.compile(r'(?:Date|When):\s*(.*?)(?:\n|$)')
        date_match = date_pattern.search(text)
        if date_match:
            date_str = date_match.group(1).strip()
            try:
                event_date = dateutil.parser.parse(date_str)
                event_details['date'] = event_date.strftime('%Y-%m-%d')
                self.event_date = event_date
            except:
                event_details['date'] = date_str
        else:
            # Use the date from the prompt
            event_details['date'] = "2025-05-18"
            self.event_date = dateutil.parser.parse("2025-05-18")
        
        # Extract event location
        location_pattern = re.compile(r'(?:Location|Venue|Where):\s*(.*?)(?:\n|$)')
        location_match = location_pattern.search(text)
        if location_match:
            location_text = location_match.group(1).strip()
            
            # Try to parse address components
            address_pattern = re.compile(r'([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+)(?:,\s*([^,]+))?')
            address_match = address_pattern.search(location_text)
            
            if address_match:
                event_details['location'] = {
                    'name': address_match.group(1).strip(),
                    'address': address_match.group(2).strip(),
                    'city': address_match.group(3).strip(),
                    'state': address_match.group(4).strip(),
                    'postal_code': address_match.group(5).strip() if address_match.group(5) else "",
                    'country': "India",  # Default country, can be extracted if available
                    'full_address': location_text
                }
            else:
                event_details['location'] = {'full_address': location_text}
        else:
            # Use the location from the prompt
            event_details['location'] = {
                'name': "ScaleOrange technologies",
                'address': "Masthan Nagar, Kavuri Hills, Madhapur",
                'city': "Hyderabad",
                'state': "Telangana",
                'postal_code': "500081",
                'country': "India",
                'full_address': "ScaleOrange technologies, Masthan Nagar, Kavuri Hills, Madhapur, Hyderabad, Telangana 500081, India"
            }
        
        # Extract event description
        description_pattern = re.compile(r'(?:Description|About):\s*(.*?)(?:\n\n|\n[A-Z])', re.DOTALL)
        description_match = description_pattern.search(text)
        if description_match:
            event_details['description'] = description_match.group(1).strip()
        
        # Extract agenda
        agenda = {}
        agenda_section = re.search(r'(?:Agenda|Schedule|Timetable|Program):(.*?)(?:\n\n|\n[A-Z]|$)', text, re.DOTALL)
        
        if agenda_section:
            agenda_text = agenda_section.group(1).strip()
            time_entries = re.findall(r'(\d{1,2}:\d{2}(?:\s*(?:AM|PM)?)\s*-\s*\d{1,2}:\d{2}(?:\s*(?:AM|PM)?))(?:\s*[-:]\s*|\s+)(.+?)(?=\n\d|\n\n|\n[A-Z]|$)', agenda_text, re.DOTALL)
            
            for time_range, activity in time_entries:
                agenda[time_range.strip()] = activity.strip()
        
        # If no structured agenda found, try simpler pattern
        if not agenda:
            time_entries = re.findall(r'(\d{1,2}:\d{2}(?:\s*(?:AM|PM)?))(?:\s*[-:]\s*|\s+)(.+?)(?=\n\d|\n\n|\n[A-Z]|$)', text, re.DOTALL)
            for time, activity in time_entries:
                agenda[time.strip()] = activity.strip()
        
        # If still no agenda, use the one from the prompt
        if not agenda:
            agenda = {
                "10:00": "11:00 AM: Workshop: Build an Event Bot using RAG",
                "11:00": "12:00 PM: Industry Connect Session - Mr. Ravi Babu, CEO, Apex Cura Healthcare",
                "12:00": "1:00 PM: Session by a Google Speaker (TBA)",
                "1:00": "2:00 PM: Lunch (Sponsored by Google)",
                "2:00": "3:00 PM: Workshop: Automating Payment Processes using Claude & MCP Server",
                "3:00": "4:00 PM: Workshop: Building Multi AI Agents",
                "11:59 PM": "Winner Announcement: Shortly after the deadline"
            }
            
        event_details['agenda'] = agenda
        
        # Create a simplified agenda for time-based queries
        self.agenda = {}
        for time_range, activity in agenda.items():
            # Extract the start time
            start_time = re.search(r'(\d{1,2}:\d{2})', time_range)
            if start_time:
                self.agenda[start_time.group(1)] = activity
        
        # Extract target audience
        audience_section = re.search(r'(?:Target Audience|Who Should Attend|Intended For):(.*?)(?:\n\n|\n[A-Z]|$)', text, re.DOTALL)
        if audience_section:
            audience_text = audience_section.group(1).strip()
            audience_items = re.findall(r'[-•*]?\s*([^-•*\n].+?)(?=\n[-•*]|\n\n|\n[A-Z]|$)', audience_text, re.DOTALL)
            if audience_items:
                event_details['target_audience'] = [item.strip() for item in audience_items]
            else:
                event_details['target_audience'] = [audience_text]
        else:
            # Use target audience from the prompt
            event_details['target_audience'] = [
                "Developers & Engineers", 
                "Tech Professionals", 
                "Students & Recent Graduates", 
                "Entrepreneurs & Product Managers"
            ]
        
        # Extract other event information like hackathon details if present
        hackathon_section = re.search(r'(?:Hackathon|Challenge|Competition):(.*?)(?:\n\n|\n[A-Z]|$)', text, re.DOTALL)
        if hackathon_section:
            hackathon_text = hackathon_section.group(1).strip()
            hackathon = {'title': re.search(r'Title:\s*(.*?)(?:\n|$)', hackathon_text)}
            if hackathon:
                event_details['hackathon'] = {'description': hackathon_text}
                
                # Extract deadline if present
                deadline_match = re.search(r'(?:Deadline|Due Date|Submission):\s*(.*?)(?:\n|$)', hackathon_text)
                if deadline_match:
                    event_details['hackathon']['deadline'] = deadline_match.group(1).strip()
                
                # Extract prizes if present
                prizes_section = re.search(r'(?:Prizes|Awards|Rewards):(.*?)(?:\n\n|\n[A-Z]|$)', hackathon_text, re.DOTALL)
                if prizes_section:
                    prizes_text = prizes_section.group(1).strip()
                    prizes = {}
                    prize_entries = re.findall(r'(First|Second|Third|1st|2nd|3rd|Winner|Runner[- ]up)(?:\s+Prize)?(?:\s*[-:]\s*|\s+)(.*?)(?=\n\d|\n\n|\n[A-Z]|$)', prizes_text, re.DOTALL)
                    
                    for position, prize in prize_entries:
                        prizes[position.strip()] = prize.strip()
                    
                    if prizes:
                        event_details['hackathon']['prizes'] = prizes
        
        # Extract venue information for locations
        locations = {}
        locations_section = re.search(r'(?:Locations|Facilities|Amenities|Venue Map):(.*?)(?:\n\n|\n[A-Z]|$)', text, re.DOTALL)
        if locations_section:
            locations_text = locations_section.group(1).strip()
            location_entries = re.findall(r'(Washroom|Restroom|Bathroom|Main Hall|Cafeteria|Registration|Reception)(?:\s*[-:]\s*|\s+)(.*?)(?=\n\d|\n\n|\n[A-Z]|$)', locations_text, re.DOTALL)
            
            for location_type, description in location_entries:
                key = location_type.lower().replace(' ', '_')
                if "washroom" in key or "restroom" in key or "bathroom" in key:
                    locations["washroom"] = description.strip()
                elif "hall" in key:
                    locations["main_hall"] = description.strip()
                elif "cafe" in key:
                    locations["cafeteria"] = description.strip()
                elif "regist" in key or "reception" in key:
                    locations["registration_desk"] = description.strip()
                else:
                    locations[key] = description.strip()
        
        # Default locations if not found in document
        if "washroom" not in locations:
            locations["washroom"] = "Exit the main hall, turn right, and you'll find the washrooms at the end of the corridor."
        if "main_hall" not in locations:
            locations["main_hall"] = "You are currently in the main hall where all sessions are being held."
        if "cafeteria" not in locations:
            locations["cafeteria"] = "The cafeteria is located on the ground floor, next to the reception area."
        if "registration_desk" not in locations:
            locations["registration_desk"] = "The registration desk is at the entrance of the main hall."
            
        # Add venue as a location if we have full address
        if 'location' in event_details and 'full_address' in event_details['location']:
            locations["venue"] = event_details['location']['full_address']
            
        self.locations = locations
        
        return event_details
        
    def extract_resumes(self, text):
        """Extract participant resume information from text"""
        resumes = []
        
        # Try to find a section with participant or resume information
        participants_section = re.search(r'(?:Participants|Attendees|Profiles|Resumes):(.*?)(?:\n\n\n|\n[A-Z]{2,}|$)', text, re.DOTALL)
        
        if participants_section:
            participants_text = participants_section.group(1).strip()
            
            # Split by common resume delimiters
            resume_chunks = re.split(r'\n\s*(?:Profile|Resume|Participant)\s*\d*\s*[:-]\s*|\n\s*(?:Name|Participant)\s*[:-]\s*', participants_text)
            
            for chunk in resume_chunks:
                if not chunk.strip():
                    continue
                    
                resume = {}
                
                # Extract name
                name_match = re.search(r'^([\w\s]+)(?:\n|$)', chunk.strip())
                if name_match:
                    resume['name'] = name_match.group(1).strip()
                else:
                    # Skip if no name found
                    continue
                
                # Extract skills
                skills_section = re.search(r'(?:Skills|Expertise|Technologies)(?:\s*[:-]\s*|\n)(.*?)(?:\n\n|\n[A-Z]|$)', chunk, re.DOTALL)
                if skills_section:
                    skills_text = skills_section.group(1).strip()
                    # Split by common delimiters
                    skills = re.split(r'[,;]|\n[-•*]', skills_text)
                    resume['skills'] = [skill.strip() for skill in skills if skill.strip()]
                
                # Extract experience
                experience_section = re.search(r'(?:Experience|Work Experience|Professional Experience)(?:\s*[:-]\s*|\n)(.*?)(?:\n\n|\n[A-Z]|$)', chunk, re.DOTALL)
                if experience_section:
                    resume['experience'] = experience_section.group(1).strip()
                
                # Extract interests
                interests_section = re.search(r'(?:Interests|Areas of Interest)(?:\s*[:-]\s*|\n)(.*?)(?:\n\n|\n[A-Z]|$)', chunk, re.DOTALL)
                if interests_section:
                    interests_text = interests_section.group(1).strip()
                    # Split by common delimiters
                    interests = re.split(r'[,;]|\n[-•*]', interests_text)
                    resume['interests'] = [interest.strip() for interest in interests if interest.strip()]
                
                # Add to resumes list if we have at least name and skills
                if 'name' in resume and ('skills' in resume or 'experience' in resume):
                    resumes.append(resume)
        
        return resumes
    
    def process_pdf(self):
        """Extract text from a PDF file and process it to get event details and resumes"""
        try:
            # Extract text from PDF
            text = self.extract_text_from_pdf()
            
            # Extract event details
            self.event_details = self.extract_event_details(text)
            logger.info(f"Extracted event details: {json.dumps(self.event_details, indent=2, default=str)}")
            
            # Extract resume information
            self.resumes = self.extract_resumes(text)
            logger.info(f"Extracted {len(self.resumes)} resumes")
            
            # Add sample data only if no resumes were found in the PDF
            if not self.resumes:
                logger.warning("No resumes found in the PDF. You may want to add resume data to your PDF.")
                # Unlike before, we won't add sample data since you requested to use data from the PDF
                
        except Exception as e:
            logger.error(f"Error processing PDF {self.pdf_path}: {str(e)}")
            raise
    
    def get_response_from_cyfuture(self, prompt):
        """Get a response from Cyfuture AI API for the given prompt"""
        try:
            conn = http.client.HTTPSConnection("api.cyfuture.ai")
            
            payload = {
                "model": "llama-8b",
                "messages": [
                    {
                        "role": "system",
                        "content": self.prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 800,
                "temperature": 0.3,  # Lower temperature for more deterministic responses
                "top_p": 0.95,
                "stream": False
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            conn.request("POST", "/v1/chat/completions", json.dumps(payload), headers)
            
            response = conn.getresponse()
            data = response.read()
            response_text = data.decode("utf-8")
            
            # Parse the JSON response
            json_data = json.loads(response_text)
            
            # Extract the message content
            if "choices" in json_data and len(json_data["choices"]) > 0:
                content = json_data["choices"][0]["message"]["content"]
                return content
            else:
                logger.error("No valid response found in API response")
                return "I'm having trouble getting a response. Please try again."
                
        except Exception as e:
            logger.error(f"Error getting response from Cyfuture: {str(e)}")
            return f"I apologize, but I encountered an error: {str(e)}"
        finally:
            conn.close()
    
    def answer_question(self, question):
        """Main method to answer user questions based on the context"""
        
        # Check if it's a feedback request
        if "feedback" in question.lower() and ("session" in question.lower() or "workshop" in question.lower()):
            return self.collect_feedback(question)
        
        # For time-related queries, get the current time
        current_time = datetime.now()
        
        # Check for event start time question
        if any(phrase in question.lower() for phrase in ["time left for event", "when does the event start", "how long until the event", "when is the event", "time until event starts"]):
            return self.get_time_until_event(current_time)
        
        # Check for lunch time question
        if "lunch" in question.lower() and ("time" in question.lower() or "left" in question.lower() or "when" in question.lower()):
            return self.get_time_until_lunch(current_time)
        
        # Check for location questions
        if "where" in question.lower() or "location" in question.lower() or "washroom" in question.lower() or "toilet" in question.lower() or "bathroom" in question.lower():
            return self.get_location_info(question)
        
        # Check for agenda question
        if "agenda" in question.lower() or "schedule" in question.lower() or "timetable" in question.lower() or "program" in question.lower():
            return self.get_agenda()
        
        # Check for similar participants question
        if "participant" in question.lower() or "similar" in question.lower() or "other attendees" in question.lower() or "who else" in question.lower() or "meet" in question.lower():
            # For this query, we need to know the user's skills/interests
            # In a real implementation, you would have the user's resume
            # For now, let's extract any skills they mention in the question
            skills = self.extract_skills_from_question(question)
            return self.find_similar_participants(skills)
        
        # Check for session recommendations
        if "recommend" in question.lower() or "which session" in question.lower() or "relevant" in question.lower() or "which workshop" in question.lower() or "suggest" in question.lower():
            # Similar to above, extract skills from the question
            skills = self.extract_skills_from_question(question)
            return self.recommend_sessions(skills)
            
        # For other questions, use Cyfuture AI to generate a response
        # Create a context for the AI
        context = f"""
Based on the event information, please answer the following question:
{question}

Please keep your answer concise and to the point. If you don't have enough information to answer the question, please say so.
"""
        
        return self.get_response_from_cyfuture(context)
    
    def _format_agenda_for_context(self):
        """Format the agenda for the context prompt"""
        agenda_text = ""
        for time, session in self.event_details.get('agenda', {}).items():
            agenda_text += f"- {time}: {session}\n"
        return agenda_text
    
    def extract_skills_from_question(self, question):
        """Extract technical skills mentioned in the question"""
        # List of common technical skills to look for
        all_skills = ["Python", "JavaScript", "Java", "C++", "C#", "Ruby", "Go", "PHP", 
                    "Swift", "Kotlin", "R", "MATLAB", "SQL", "NoSQL", "MongoDB", 
                    "PostgreSQL", "MySQL", "Oracle", "React", "Angular", "Vue", 
                    "Node.js", "Express", "Django", "Flask", "Spring", "ASP.NET", 
                    "TensorFlow", "PyTorch", "Keras", "scikit-learn", "Pandas", 
                    "NumPy", "SciPy", "Machine Learning", "Deep Learning", "NLP", 
                    "Computer Vision", "Reinforcement Learning", "AI", "Data Science", 
                    "Big Data", "Hadoop", "Spark", "AWS", "Azure", "GCP", "Docker", 
                    "Kubernetes", "Jenkins", "Git", "CI/CD", "DevOps", "Blockchain", 
                    "Cybersecurity", "UI/UX", "Mobile Development", "Web Development",
                    "RAG", "Chatbot", "LLM", "BERT", "GPT", "Transformers", "API"]
        
        # Check for skills in the question
        mentioned_skills = []
        for skill in all_skills:
            if skill.lower() in question.lower():
                mentioned_skills.append(skill)
                
        # If no specific skills found, check for broader areas
        if not mentioned_skills:
            broad_areas = ["AI", "Machine Learning", "Data Science", "Web Development", 
                          "Mobile Development", "DevOps", "Cloud", "Database", 
                          "Frontend", "Backend", "Full Stack", "Security", "UI/UX"]
            
            for area in broad_areas:
                if area.lower() in question.lower():
                    mentioned_skills.append(area)
        
        return mentioned_skills
    
    def find_similar_participants(self, skills):
        """Find participants with similar skills or interests"""
        if not skills:
            return "I need to know what technical areas you're interested in to find similar participants. Could you please mention some of your skills or interests?"
        
        similar_participants = []
        for resume in self.resumes:
            # Check for skill match
            matches = []
            for skill in skills:
                # Check in skills
                if 'skills' in resume and any(skill.lower() in s.lower() for s in resume["skills"]):
                    matches.append(skill)
                # Check in interests
                elif 'interests' in resume and any(skill.lower() in i.lower() for i in resume["interests"]):
                    matches.append(skill)
                    
            if matches:
                similar_participants.append({
                    "name": resume["name"],
                    "matches": matches,
                    "skills": resume.get("skills", []),
                    "experience": resume.get("experience", "Not specified")
                })
        
        if similar_participants:
            response = "Here are participants who've worked on similar technical areas:\n\n"
            for participant in similar_participants:
                response += f"- {participant['name']}: {', '.join(participant['skills'])} with {participant['experience']}\n"
            return response
        else:
            return "I couldn't find any participants with the mentioned skills. Try specifying different skills or interests."
    
    def recommend_sessions(self, skills):
        """Recommend workshop sessions based on skills"""
        if not skills:
            return "I need to know what technical areas you're interested in to recommend sessions. Could you please mention some of your skills or interests?"
        
        # Define keywords for each session
        session_keywords = {}
        
        # Build keywords from actual agenda items
        for time, session in self.event_details.get('agenda', {}).items():
            # Extract key technical terms from session title
            keywords = []
            session_lower = session.lower()
            
            if "rag" in session_lower or "event bot" in session_lower:
                keywords.extend(["RAG", "Chatbot", "NLP", "AI", "ML", "Python", "LLM"])
            elif "claude" in session_lower or "payment" in session_lower:
                keywords.extend(["Automation", "Payments", "Claude", "LLM", "API"])
            elif "multi ai" in session_lower or "agent" in session_lower:
                keywords.extend(["Agents", "Multi-agent", "AI", "ML", "LLM"])
            elif "google" in session_lower:
                keywords.extend(["Google", "Cloud", "ML", "AI"])
            elif "industry" in session_lower or "connect" in session_lower:
                keywords.extend(["Industry", "Business"])
            
            # Add domain-specific keywords based on session title
            for domain in ["healthcare", "finance", "education", "retail", "manufacturing"]:
                if domain in session_lower:
                    keywords.append(domain.capitalize())
            
            session_keywords[session] = keywords
        
        # Find matching sessions
        recommended_sessions = []
        for session, keywords in session_keywords.items():
            for skill in skills:
                if any(skill.lower() in keyword.lower() for keyword in keywords):
                    if session not in recommended_sessions:
                        recommended_sessions.append(session)
        
        if recommended_sessions:
            response = "Based on your interests, I recommend these sessions:\n\n"
            for session in recommended_sessions:
                # Find the time for this session
                time = next((time for time, s in self.event_details.get('agenda', {}).items() if s == session), "")
                response += f"- {time}: {session}\n"
            return response
        else:
            return "Based on the skills you've mentioned, I don't have specific session recommendations. All sessions may be of general interest. Is there a particular topic you're curious about?"
    
    def get_agenda(self):
        """Return the event agenda"""
        if not self.event_details.get('agenda'):
            return "I'm sorry, but the agenda information is not available."
            
        response = f"Here's the meeting agenda for {self.event_details.get('title', 'the event')}:\n\n"
        for time, session in self.event_details.get('agenda', {}).items():
            response += f"- {time}: {session}\n"
        return response
    
    def get_location_info(self, question):
        """Return location information based on the question"""
        # Check if user is asking about the venue/location of the event
        if any(word in question.lower() for word in ["venue", "where is the event", "event location", "where is it held", "address"]):
            if "location" in self.event_details and "full_address" in self.event_details["location"]:
                return f"The event is being held at {self.event_details['location']['name']} located at {self.event_details['location']['full_address']}"
            else:
                return f"The event location information is not available."
            
        # Simple keyword matching to determine what location the user is asking about
        location_keyword = None
        
        if "washroom" in question.lower() or "toilet" in question.lower() or "bathroom" in question.lower() or "restroom" in question.lower():
            location_keyword = "washroom"
        elif "main hall" in question.lower() or "session" in question.lower() or "conference" in question.lower():
            location_keyword = "main_hall"
        elif "food" in question.lower() or "cafeteria" in question.lower() or "eat" in question.lower() or "canteen" in question.lower():
            location_keyword = "cafeteria"
        elif "register" in question.lower() or "registration" in question.lower() or "reception" in question.lower():
            location_keyword = "registration_desk"
        elif "venue" in question.lower() or "location" in question.lower() or "address" in question.lower() or "where" in question.lower():
            location_keyword = "venue"
        
        if location_keyword and location_keyword in self.locations:
            return self.locations[location_keyword]
        else:
            return "I'm not sure about that location. I can help you find the washroom, main hall, cafeteria, or registration desk. I can also tell you about the venue location. Please ask about one of these locations."
    
    def get_time_until_event(self, current_time):
        """Calculate and return the time remaining until the event starts"""
        # Check if we have event date information
        if not hasattr(self, 'event_date'):
            if 'date' in self.event_details:
                try:
                    self.event_date = dateutil.parser.parse(self.event_details['date'])
                except:
                    return f"The event is scheduled for {self.event_details.get('date', 'an upcoming date')}. Please check the event details for more information."
            else:
                return "I'm sorry, but I don't have the event date information."
        
        # Get today's date
        today = current_time.date()
        event_date = self.event_date.date()
        
        if event_date > today:
            # Event is in the future
            days_until_event = (event_date - today).days
            if days_until_event > 1:
                return f"The event is {days_until_event} days away, on {event_date.strftime('%B %d, %Y')}. It starts at 10:00 AM."
            elif days_until_event == 1:
                return f"The event is tomorrow, {event_date.strftime('%B %d, %Y')}. It starts at 10:00 AM."
            else:
                # This shouldn't happen given the comparison above, but just in case
                return f"The event is today, {event_date.strftime('%B %d, %Y')}. It starts at 10:00 AM."
        elif event_date < today:
            # Event is in the past
            return f"The event has already taken place on {event_date.strftime('%B %d, %Y')}."
        else:
            # Event is today
            # Find the first item in the agenda to determine start time
            start_time = "10:00"  # Default start time
            if self.agenda:
              start_time = min(self.agenda.keys())
              try:
                event_start_time = datetime.combine(today, datetime.strptime(start_time, "%H:%M").time())
                
                if current_time < event_start_time:
                    # Event hasn't started yet
                    time_diff = event_start_time - current_time
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if hours > 0:
                        return f"The event starts today in {hours} hours and {minutes} minutes, at {start_time} AM."
                    else:
                        return f"The event starts today in {minutes} minutes, at {start_time} AM."
                else:
                    # Find current ongoing session
                    current_session = self.get_current_session(current_time)
                    if current_session:
                        return f"The event has already started. Current session: {current_session}"
                    else:
                        return "The event has already started today."
              except Exception as e:
                logger.error(f"Error calculating time until event: {str(e)}")
                return f"The event is scheduled for today, {event_date.strftime('%B %d, %Y')}."
    
    def get_current_session(self, current_time):
        """Determine the current ongoing session based on the time"""
        if not self.agenda:
            return None
            
        # Convert agenda times to datetime objects
        session_times = []
        for time_str, session in self.agenda.items():
            try:
                session_time = datetime.strptime(time_str, "%H:%M").time()
                session_times.append((datetime.combine(current_time.date(), session_time), session))
            except ValueError:
                continue
                
        # Sort by time
        session_times.sort(key=lambda x: x[0])
        
        # Find the current session
        current_session = None
        next_session_time = None
        
        for i, (session_time, session) in enumerate(session_times):
            if session_time <= current_time:
                current_session = session
                if i < len(session_times) - 1:
                    next_session_time = session_times[i + 1][0]
            else:
                break
                
        if current_session and next_session_time and current_time < next_session_time:
            return current_session
        return None
        
    def get_time_until_lunch(self, current_time):
        """Calculate and return the time remaining until lunch"""
        # Check if we have event date information
        if not hasattr(self, 'event_date'):
            if 'date' in self.event_details:
                try:
                    self.event_date = dateutil.parser.parse(self.event_details['date'])
                except:
                    return f"The event is scheduled for {self.event_details.get('date', 'an upcoming date')}. Please check the event details for more information."
            else:
                return "I'm sorry, but I don't have the event date information."
                
        # Try to find lunch in the agenda
        lunch_time = None
        lunch_entry = None
        
        for time_entry, session in self.event_details.get('agenda', {}).items():
            if "lunch" in session.lower():
                lunch_entry = session
                # Extract start time from the time range
                start_time = re.search(r'(\d{1,2}:\d{2})', time_entry)
                if start_time:
                    lunch_time = start_time.group(1)
                break
                
        if not lunch_time:
            # Default lunch time if not found in agenda
            lunch_time = "13:00"
        
        # Get today's date
        today = current_time.date()
        event_date = self.event_date.date()
        
        if event_date != today:
            if event_date > today:
                days_until_event = (event_date - today).days
                return f"The event is {days_until_event} days away, on {event_date.strftime('%B %d, %Y')}. Lunch will be at {lunch_time}."
            else:
                return f"The event has already taken place on {event_date.strftime('%B %d, %Y')}."
        
        # If the event is today, calculate time until lunch
        try:
            lunch_datetime = datetime.combine(today, datetime.strptime(lunch_time, "%H:%M").time())
            # Assume lunch ends 1 hour after it starts
            lunch_end_datetime = lunch_datetime + timedelta(hours=1)
            
            if current_time < lunch_datetime:
                time_diff = lunch_datetime - current_time
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    return f"Lunch will begin in {hours} hours and {minutes} minutes. It's scheduled for {lunch_time}."
                else:
                    return f"Lunch will begin in {minutes} minutes. It's scheduled for {lunch_time}."
            elif current_time >= lunch_datetime and current_time < lunch_end_datetime:
                time_diff = lunch_end_datetime - current_time
                hours, remainder = divmod(time_diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    return f"Lunch is currently ongoing! It will end in {hours} hours and {minutes} minutes."
                else:
                    return f"Lunch is currently ongoing! It will end in {minutes} minutes."
            else:
                return f"Lunch time ({lunch_time}) has already passed for today."
        except Exception as e:
            logger.error(f"Error calculating time until lunch: {str(e)}")
            return f"Lunch is scheduled for {lunch_time}."
            
    def collect_feedback(self, question):
        """Collect and store feedback for different sessions"""
        # Try to identify which session the feedback is for
        session_name = None
        for session in self.event_details.get('agenda', {}).values():
            if session.lower() in question.lower():
                session_name = session
                break
        
        if not session_name:
            return "I'd be happy to collect your feedback. Could you please specify which session you attended?"
        
        # Ask for feedback
        return f"Thank you for attending the '{session_name}' session! I'd love to hear your feedback.\n\n" \
               f"How would you rate the session on a scale of 1-5? What did you like about it, and is there anything that could be improved? Your feedback is valuable to us!"

def validate_pdf(pdf_path):
    """Validate that the PDF exists and is readable"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as file:
            PyPDF2.PdfReader(file)
    except Exception as e:
        raise ValueError(f"Invalid PDF file: {str(e)}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Event Bot for handling queries about an event and participants")
    parser.add_argument("-p", "--pdf", required=True, help="Path to a PDF file with event details and resumes")
    parser.add_argument("-k", "--api-key", required=True, help="Cyfuture AI API key")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    try:
        # Validate PDF
        validate_pdf(args.pdf)
        
        # Create the event bot
        logger.info(f"Initializing EventBot with PDF: {args.pdf}")
        bot = EventBot(args.pdf, args.api_key)
        
        print("=" * 50)
        print(f"Welcome to the Event Bot for {bot.event_details.get('title', 'the Event')}!")
        print("I can help you with information about the event, schedule, participants, and more.")
        print("Type 'exit' or 'quit' to end the conversation.")
        print("=" * 50)
        
        while True:
            # Get user question
            question = input("\nYou: ")
            
            # Check if user wants to exit
            if question.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("\nEvent Bot: Thank you for using the Event Bot. Have a great day!")
                break
            
            # Get answer from the bot
            try:
                logger.debug(f"Processing question: {question}")
                answer = bot.answer_question(question)
                
                # Display the answer
                print(f"\nEvent Bot: {answer}")
            except Exception as e:
                logger.error(f"Error processing question: {str(e)}")
                print(f"\nEvent Bot: I'm sorry, I encountered an error while processing your question. Please try again.")
                
    except FileNotFoundError as e:
        logger.error(str(e))
        print(f"Error: {str(e)}")
    except ValueError as e:
        logger.error(str(e))
        print(f"Error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print(f"An unexpected error occurred: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()