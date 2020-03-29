from typing import NamedTuple, List, Dict, Optional, Any
import os.path
import pickle
from datetime import datetime
import base64
import html
import re

from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import dateutil.parser

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class Attachment(NamedTuple):
    attachment_id: str
    message_id: str
    user_id: str
    file_name: str
    service: Resource

    def save_to_file(self, path):

        attachment = (
            self.service.users()
            .messages()
            .attachments()
            .get(id=self.attachment_id, userId=self.user_id, messageId=self.message_id)
            .execute()
        )
        file_data = base64.urlsafe_b64decode(attachment["data"].encode("utf-8"))
        with open(path, "wb") as f:
            f.write(file_data)


class Email(NamedTuple):
    from_address: str
    to_address: str
    cc_addresses: tuple
    subject: str
    snippet: str
    body: str
    date_receieved: datetime
    raw_message: Dict[str, Any]
    gmail_message_id: str
    attachments: List[Attachment]

    @property
    def forwarded_from_address(self):
        pattern = r"From: <(\S+@\S+)>"
        if re.findall(pattern, self.snippet):
            return re.findall(pattern, self.snippet)[0]
        return ""


def get_service() -> Resource:
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("gmail", "v1", credentials=creds)
    return service


def get_from_headers(headers: List[Dict[str, str]], value: str) -> str:
    for h in headers:
        if h["name"] == value:
            return h["value"]
    return ""


def get_attachments_from_message(
    message, service: Resource, user_id: str
) -> List[Attachment]:
    msg_id = message["id"]
    attachments: List[Attachment] = []
    if "parts" not in message["payload"]:
        return attachments
    for part in message["payload"]["parts"]:
        if part["filename"] and part["body"] and part["body"]["attachmentId"]:
            file_name = part["filename"]
            attachment = Attachment(
                attachment_id=part["body"]["attachmentId"],
                message_id=msg_id,
                user_id=user_id,
                file_name=file_name,
                service=service,
            )
            attachments.append(attachment)
    return attachments


def get_emails(service: Resource) -> List[Email]:
    users = service.users()
    messages = users.messages()
    message_specs = messages.list(userId="me").execute()["messages"]
    message_ids = [ms["id"] for ms in message_specs]
    emails: List[Email] = []
    user_id = "me"
    for message_id in message_ids:
        message = messages.get(id=message_id, userId=user_id).execute()
        payload = message["payload"]
        headers = payload["headers"]

        from_address = get_from_headers(headers, "From")
        to_address = get_from_headers(headers, "To")
        raw_cc_addresses = get_from_headers(headers, "Cc")
        if raw_cc_addresses:
            cc_addresses = tuple(raw_cc_addresses.split(","))
        else:
            cc_addresses = ()
        subject = get_from_headers(headers, "Subject")
        date_receieved = dateutil.parser.parse(get_from_headers(headers, "Date"))
        attachments = get_attachments_from_message(message, service, user_id=user_id)
        email = Email(
            from_address=from_address,
            to_address=to_address,
            cc_addresses=cc_addresses,
            subject=subject,
            date_receieved=date_receieved,
            snippet=html.unescape(message["snippet"]),
            body="",
            raw_message=message,
            gmail_message_id=message["id"],
            attachments=attachments,
        )
        emails.append(email)
    return emails


def main():

    service = get_service()
    emails = get_emails(service)


if __name__ == "__main__":
    main()
