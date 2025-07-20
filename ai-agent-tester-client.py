from google.cloud import aiplatform
from google.cloud.aiplatform_v1beta1 import ReasoningEngineServiceClient
from time import sleep
import google.auth

credentials, project_id = google.auth.default()
location = "us-central1"
reasoning_engine_id = "3749695290530070528"

client = ReasoningEngineServiceClient(
    client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"},
    credentials=credentials
)

endpoint = f"projects/{project_id}/locations/{location}/reasoningEngines/{reasoning_engine_id}"

# Test session creation
try:
    session_response = client.create_session(name=endpoint, request={"user_id": "test_user"})
    operation_name = session_response.name
    print(f"Operation Name: {operation_name}")
    operation = client._transport.operations_client.get_operation(operation_name)
    while not operation.done:
        print("Waiting for operation to complete...")
        sleep(2)
        operation = client._transport.operations_client.get_operation(operation_name)
    session_id = operation.response.session_id or operation.response.id or operation.name.split("sessions/")[1].split("/")[0]
    print(f"Session ID: {session_id}")
except Exception as e:
    print(f"Session creation error: {e}")
    session_id = ''

# Test payloads
payloads = [
    {"contents": [{"parts": [{"text": "What is the weather in San Francisco?"}], "role": "user"}], "session_id": session_id} if session_id else {"contents": [{"parts": [{"text": "What is the weather in San Francisco?"}], "role": "user"}]},
    {"query": "What is the weather in San Francisco?"}
]

for payload in payloads:
    print(f"\nTesting payload: {payload}")
    try:
        response = client.query(name=endpoint, query_request=payload)
        print(f"Query Response: {response}")
    except Exception as e:
        print(f"Query Error: {e}")
    try:
        response = client.stream_query(name=endpoint, request=payload)
        print(f"Stream Query Response:")
        for chunk in response:
            print(f"Chunk: {chunk}")
    except Exception as e:
        print(f"Stream Query Error: {e}")