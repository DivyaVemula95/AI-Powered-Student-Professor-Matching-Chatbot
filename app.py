from flask import Flask, request, jsonify
import requests
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import openai

app = Flask(__name__)

# Load NLP Model for Skill Extraction
nlp = spacy.load("en_core_web_sm")

# Replace these with your Azure AD app details
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
TENANT_ID = "your_tenant_id"

# OpenAI API Key
openai.api_key = "your_openai_api_key"

# SharePoint site and list details
SITE_URL = "https://mygsu.sharepoint.com/teams/CISGRAHiringData/"
LIST_NAME = "Pending List Spring 25 and Fall 24 (Incoming and current)"

# Request an access token for SharePoint
def get_access_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

# Retrieve Student Profiles from SharePoint
def get_students():
    access_token = get_access_token()
    if not access_token:
        raise Exception("Failed to retrieve access token")

    HEADERS = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{SITE_URL}/_api/web/lists/getbytitle('{LIST_NAME}')/items", headers=HEADERS)
    return response.json().get("value", [])

# Extract Skills from Query using NLP
def extract_skills(query):
    doc = nlp(query)
    skills = [ent.text for ent in doc.ents if ent.label_ == "SKILL"]
    return skills

# Match Students Using TF-IDF and Cosine Similarity
def match_students(professor_query, student_profiles):
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([professor_query] + student_profiles)
    cosine_sim = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    return [student_profiles[i] for i in cosine_sim.argsort()[-3:][::-1]]

# Generate Chatbot Response with OpenAI GPT-4
def generate_response(professor_query, matched_students):
    prompt = f"""
    You are a chatbot helping professors find students. 
    The professor needs a student with: {professor_query}.
    Matching students: {', '.join(matched_students)}.
    Summarize the matches and ask the professor to select a student.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    return response.choices[0].message.content.strip()

# Chatbot API Endpoint
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    professor_query = data.get('query', '')

    # Step 1: Extract Skills from Query
    skills = extract_skills(professor_query)

    # Step 2: Fetch Students from SharePoint
    students = get_students()
    student_profiles = [s["Skills"] for s in students]

    # Step 3: Match Students Using ML
    matched_students = match_students(professor_query, student_profiles)

    # Step 4: Generate Response Using GPT-4
    response = generate_response(professor_query, matched_students)

    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)
