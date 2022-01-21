from typing import List, Tuple
from bs4 import BeautifulSoup
import logging
import os
import requests

logger = logging.getLogger(__name__)

class StoryPark:

    def __init__(self) -> None:
        self._s = requests.Session()
        self._base_url = os.getenv("BASEURL", "https://app.storypark.com")
        self._authenticity_token = "" # Set during login

    def login(self, username: str, password: str) -> None:
        url = f"{self._base_url}/users/sign_in"
        logger.info("Sending GET request to %s to get authenticity token", url)
        r = self._s.get(url, timeout=60)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        elem = soup.find("input", attrs={"name": "authenticity_token"})
        if not elem:
            logger.error("Unable to find authenticity token input, HTML was: %s", r.text)
            raise RuntimeError("Unable to find authenticity token input")
        self._authenticity_token = elem.get("value", "")
        if not self._authenticity_token:
            logger.error("Found authenticity token input but value was empty!")
            raise RuntimeError("Authencity token value was empty!")
        logger.debug("Found authenticity token '%s'", self._authenticity_token)

        data = {
            "user[email]": username,
            "user[password]": password,
            "authenticity_token": self._authenticity_token
        }
        r = self._s.post(url, data=data, timeout=60)
        r.raise_for_status()

        logger.debug(r.status_code)
        logger.debug(r.text)

    def logout(self) -> None:
        url = f"{self._base_url}/users/sign_out"
        data = {
            "_method": "delete",
            "authenticity_token": self._authenticity_token
        }
        logger.info("Logging out of StoryPark")
        logger.debug("Sending logout request to %s, body is: %s", url, data)
        self._s.post(url, data=data)

    def get_story_ids(self, child_id: str, page_token: str="") -> Tuple[List[str], str]:
        logger.info("Getting story IDs for child '%s', with page token '%s'", child_id, page_token)
        url = f"{self._base_url}/api/v3/children/{child_id}/stories?sort_by=updated_at&story_type=all&page_token={page_token}"
        r = self._s.get(url, timeout=60)
        r.raise_for_status()
        js = r.json()

        next_page_token = js["next_page_token"]
        ids = [story["id"] for story in js["stories"]]
        return (ids, next_page_token)

    def get_story(self, story_id: str) -> dict:
        logger.info("Getting story details for story %s", story_id)
        url = f"{self._base_url}/api/v3/activity/{story_id}"
        r = self._s.get(url, timeout=60)
        r.raise_for_status()
        js = r.json()
        return js["activity"]

        
