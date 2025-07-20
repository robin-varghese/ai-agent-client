# app.py (FINAL - This is the one)

import os
import uuid
import requests
import json
import logging
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

from vertexai import init as vertex_init
from vertexai import agent_engines

import google.auth
import google.auth.transport.requests

load_dotenv()

# --- Configuration ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION")

if not GCP_PROJECT_ID or not GCP_LOCATION:
    raise ValueError("GCP_PROJECT_ID and GCP_LOCATION must be set in the .env file.")

# --- Flask App Initialization ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Initialize the Vertex AI SDK ---
vertex_init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

chat_sessions = {}

def get_auth_token():
    credentials, project_id = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

# --- API Routes ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/agents", methods=["GET"])
def list_agents():
    """Lists agents using the reliable agent_engines SDK method."""
    try:
        all_agents = agent_engines.list()
        agents_list = [
            {"id": agent.name.split('/')[-1], "display_name": agent.display_name, "full_name": agent.name}
            for agent in all_agents
        ]
        return jsonify(agents_list)
    except Exception as e:
        app.logger.error(f"Error listing agents: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/agent/<agent_id>", methods=["GET"])
def get_agent_details(agent_id: str):
    """Gets details for a specific agent using the SDK."""
    try:
        agent = agent_engines.get(agent_id)
        details = {"display_name": agent.display_name, "type": "Vertex AI Agent (ADK)"}
        return jsonify(details)
    except Exception as e:
        app.logger.error(f"Error getting agent details: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handles a chat interaction via the Reasoning Engine REST API."""
    data = request.json
    agent_full_name = data.get("agent_full_name")
    prompt = data.get("prompt")

    if not agent_full_name or not prompt:
        return jsonify({"error": "agent_full_name and prompt are required"}), 400

    agent_short_id = agent_full_name.split('/')[-1]
    user_id = "webapp-user-001"
    
    if agent_short_id not in chat_sessions:
        chat_sessions[agent_short_id] = str(uuid.uuid4())
    session_id = chat_sessions[agent_short_id]

    try:
        token = get_auth_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        # --- THE FINAL FIX: The endpoint MUST be constructed with the full resource path ---
        api_endpoint = (
            f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1/{agent_full_name}:streamQuery"
        )
        
        # The payload for streamQuery is a flat object.
        payload = {
            "message": prompt,
            "user_id": user_id,
            "session_id": session_id,
        }

        app.logger.info(f"Calling endpoint: {api_endpoint}")
        app.logger.info(f"With payload: {json.dumps(payload)}")

        response = requests.post(api_endpoint, headers=headers, json=payload)
        response.raise_for_status()

        # Parse the JSONL response from streamQuery
        full_response_text = ""
        last_text_chunk = ""
        for line in response.text.strip().split('\n'):
            try:
                chunk = json.loads(line)
                app.logger.info(f"Received stream chunk: {chunk}")
                if "output" in chunk and isinstance(chunk["output"], dict):
                    if "text" in chunk["output"]:
                        last_text_chunk = chunk["output"]["text"]
            except json.JSONDecodeError:
                continue
        full_response_text = last_text_chunk if last_text_chunk else "Agent processed the request but returned no parsable text."
        
        return jsonify({"response": full_response_text})

    except requests.exceptions.HTTPError as http_err:
        error_message = "Unknown API Error"
        try:
            error_content = http_err.response.json()
            app.logger.error(f"HTTP error occurred: {error_content}")
            if isinstance(error_content, dict):
                 error_message = error_content.get("error", {}).get("message", "Unknown API error")
        except json.JSONDecodeError:
            error_message = "Could not parse error response from API."
            app.logger.error(f"Failed to parse JSON from error response: {http_err.response.text}")
        return jsonify({"error": f"API Error: {error_message}"}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in /api/chat: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)