from function_app import extract_event_from_email
import azure.functions as func
import json

from .config import OPENAI_API_KEY


def test_hello_world_event():
    # Construct a mock HTTP request.
    data = {
        "body_html": "Say hello to the world on 2/26/2024 at 8 pm",
        "openai_key": OPENAI_API_KEY,
    }
    json_data = json.dumps(data)
    req = func.HttpRequest(
        method="GET",
        body=json_data.encode("utf-8"),
        url="/api/emailpost",
    )

    # Call the function.
    func_call = extract_event_from_email.build().get_user_function()
    response = func_call(req)
    print(response.get_body())
    assert response.status_code == 200
