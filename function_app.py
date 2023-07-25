import azure.functions as func
import logging
import re
import json
import openai
from bs4 import BeautifulSoup
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.formrecognizer import DocumentAnalysisClient

endpoint = "https://sanchtmi.cognitiveservices.azure.com/"

app = func.FunctionApp()

@app.function_name(name="ExtractEventFromEmail")
@app.route(route="emailpost", auth_level=func.AuthLevel.ANONYMOUS)
def extract_event_from_email(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")
    logging.info(f'{req=}')


    req_body = req.get_json()

    body_html = req_body.get("body_html")
    soup = BeautifulSoup(body_html, 'html.parser')
    body_text = soup.get_text(separator='\n').strip()
    # remove whitespaces that contain multiple newlines
    body_text = re.sub(r'\s*\n\s*', '\n', body_text)

    ocr_text = ""
    if req_body.get("attachment") is not None:
        try:
            azure_key = req_body.get("azure_key")
            document_analysis_client = DocumentAnalysisClient(
                endpoint=endpoint, credential=AzureKeyCredential(azure_key)
            )

            poller = document_analysis_client.begin_analyze_document_from_url(
                model_id="prebuilt-read", document_url=req_body.get("attachment")
            )
            ocr_result = poller.result()
            ocr_text = ocr_result.content
            logging.info(f'{ocr_result=}')
        except HttpResponseError as e:
            logging.error(f'Attachment OCR failed with error {e}')

    openai.api_key = req_body.get("openai_key")

    prompt = f"""I received the following email containing a calendar event:
###
Received: {req_body.get("raw_date")}
Subject: {req_body.get("subject")}
Body:
{body_text}
Attachment:
{ocr_text}

###

Extract details about the event in the following format:

Example:
{{
"StartTime": "2023-01-21T19:56-07:00",
"EndTime": "2023-01-21T20:56-07:00",
"Summary": "Dentist appointment",
"Address": "200 Infinity Way Apt 2324, Mountain View, CA"
}}

Example:
{{
"StartTime": "2023-01-27T13:29-07:00",
"EndTime": "2023-01-27T14:29-07:00",
"Summary": "Reservation at Fiero Cafe, San Mateo",
"Address": ""
}}

Example:
{{
"StartTime": "",
"EndTime": "",
"Summary": "[Movie] A Man Called Otto",
"Address": ""
}}

###
Infer the time of event based on when the email was received. For example if the email was received on tuesday and the event mentions friday pick the date of the upcoming friday. If the time cannot be inferred unambiguosly then leave the field empty.
If the event does not have a physical address, leave the address field empty.
If the duration of the event cannot be inferred from the email, assume duration is 1 hour.

Details:"""

    logging.info(f'{prompt=}')
    

    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=100,
        temperature=0.0,
    )

    logging.info(f'{response=}')

    ret_json = json.loads(response['choices'][0]['text'])
    ret_json['body_text'] = body_text
    ret_json['ocr_text'] = ocr_text

    return func.HttpResponse(
        body=json.dumps(ret_json),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )
