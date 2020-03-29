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
    date_receieved: Optional[datetime]
    raw_message: Dict[str, Any]
    gmail_message_id: str
    attachments: List[Attachment]

    @property
    def forwarded_from_address(self):
        pattern = r"From: <(\S+@\S+)>"
        if re.findall(pattern, self.snippet):
            return re.findall(pattern, self.snippet)[0]
        return ""

    @property
    def slug(self):
        if self.forwarded_from_address:
            from_address = self.forwarded_from_address
        else:
            from_address = self.from_address

        raw = f"{self.gmail_message_id}.{from_address}.{self.subject}"
        return re.sub(r"\W", "-", raw)


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


def download_all_message_specs(service: Resource, query) -> List[Dict[str, str]]:
    users = service.users()
    message_specs = []
    response = users.messages().list(userId="me", q=query).execute()
    if "messages" in response:
        message_specs.extend(response["messages"])
    while "nextPageToken" in response:
        page_token = response["nextPageToken"]
        response = (
            service.users()
            .messages()
            .list(userId="me", pageToken=page_token, q=query)
            .execute()
        )
        message_specs.extend(response["messages"])
    return message_specs


def get_emails(service: Resource, query=None) -> List[Email]:
    users = service.users()
    message_specs = download_all_message_specs(service, query)

    message_ids = [ms["id"] for ms in message_specs]
    emails: List[Email] = []
    user_id = "me"
    for message_id in message_ids:
        message = users.messages().get(id=message_id, userId=user_id).execute()
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
        try:
            date_receieved = dateutil.parser.parse(get_from_headers(headers, "Date"))
        except:
            date_receieved = None
        attachments = get_attachments_from_message(message, service, user_id=user_id)
        email = Email(
            from_address=from_address,
            to_address=to_address,
            cc_addresses=cc_addresses,
            subject=subject,
            date_receieved=date_receieved,
            snippet=html.unescape(message["snippet"]),
            raw_message=message,
            gmail_message_id=message["id"],
            attachments=attachments,
        )
        emails.append(email)
    return emails


def get_already_visited(path: str = "already_visited.csv") -> List[str]:
    try:
        with open(path) as f:
            return [l.strip() for l in f]
    except FileNotFoundError:
        return []


def update_already_visited(emails: List[Email], path: str = "already_visited.csv"):
    already_visited = set(get_already_visited())
    with open(path, "a") as f:
        for email in emails:
            if email.slug not in already_visited:
                f.write(email.slug + "\n")


def download_all_attachments_last_n_days(n: int = 2, download_dir: str = ""):
    query = f"newer_than:{n}d"
    service = get_service()
    emails = get_emails(service, query=query)
    already_visited = set(get_already_visited())
    for email in emails:
        if email.slug not in already_visited:
            for attachment in email.attachments:
                path = f"{download_dir}/{email.slug}.{attachment.file_name}"
                attachment.save_to_file(path)
    update_already_visited(emails)


def main():
    download_all_attachments_last_n_days(n=2, download_dir="data")


if __name__ == "__main__":
    main()
