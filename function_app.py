import azure.functions as func
import logging
import re
import json
from openai import OpenAI
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
    logging.info(f"{req=}")

    req_body = req.get_json()

    body_html = req_body.get("body_html")
    soup = BeautifulSoup(body_html, "html.parser")
    body_text = soup.get_text(separator="\n").strip()
    # remove whitespaces that contain multiple newlines
    body_text = re.sub(r"\s*\n\s*", "\n", body_text)

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
            logging.info(f"{ocr_result=}")
        except HttpResponseError as e:
            logging.error(f"Attachment OCR failed with error {e}")

    api_key = req_body.get("openai_key")

    with open("system_prompt.txt", "r") as f:
        system_prompt = f.read()

    prompt = f"""I received the following email containing a calendar event:
###
Received: {req_body.get("raw_date")}
Subject: {req_body.get("subject")}
Body:
{body_text}
Attachment:
{ocr_text}"""

    logging.info(f"{prompt=}")
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    logging.info(f"{response=}")

    ret_json = json.loads(response.choices[0].message.content)
    ret_json["body_text"] = body_text
    ret_json["ocr_text"] = ocr_text

    return func.HttpResponse(
        body=json.dumps(ret_json),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )
