import logging
import json
import mimetypes
import os
import pathlib
import requests
import sys

from slugify import slugify

from storypark import StoryPark

# Setup logging to stdout
loglevel = os.getenv("LOGLEVEL", "INFO")
root = logging.getLogger()
root.setLevel(loglevel)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(loglevel)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

logger = logging.getLogger(__name__)
storypark = StoryPark()

def download_file(url, filepath) -> None:
    logger.info("Attempting to download %s to %s", url, filepath)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024): 
                f.write(chunk)

def download_all_stories(child_id, root_path) -> None:
    page_token = ""
    while True:
        ids, page_token = storypark.get_story_ids(child_id, page_token)
        for id in ids:
            story = storypark.get_story(id)
            # Directory name is "{date}.{storyid}.{slugtitle}" eg "123456.2021-01-22T21:28:00Z.some-title-here"
            iso_datetcreated = story["created_at"].split(".")[0].replace(":", "-") + "Z" # Keep only the date and HH:MM:SS part, removing colons for safe directory names
            title = slugify(story["title"])
            dirname = f"{iso_datetcreated}.{id}"
            if title:
                dirname = f"{dirname}.{title}"
            outdir = root_path / dirname
            if not outdir.exists():
                logger.info("Output directory %s does not exist, creating it", outdir)
                outdir.mkdir()

            logger.info("Dumping story details to info.json")
            with open(outdir / "info.json", "w", encoding="utf-8") as f:
                json.dump(story, f, ensure_ascii=False, indent=4)

            if len(story["media"]) == 0:
                logger.info("Story contains no media items to download")
                continue

            for media in story["media"]:
                ext = mimetypes.guess_extension(media["content_type"])
                filename = f"{media['file_name']}{ext or ''}"
                filepath = outdir / filename
                if filepath.exists():
                    logger.info("File %s already exists, skipping download", filepath)
                    continue

                url = media["original_url"]
                try:
                    download_file(url, filepath)
                except requests.exceptions.HTTPError as e:
                    logger.error("403 Forbidden received when attempting original quality URL, trying resized URL")
                    url = media["resized_url"]
                    try:
                        download_file(url, filepath)
                    except requests.exceptions.HTTPError as e:
                        logger.error("Resized URL also failed, ignoring media item")
                        continue
        
        if not page_token:
            break

def main() -> None:
    child_id = os.getenv("CHILDID")
    username = os.getenv("UNAME")
    password = os.getenv("PASSWORD")
    root_path_env = os.getenv("ROOTPATH")

    if not child_id:
        raise RuntimeError("A child ID must be provided in environment variable CHILDID")

    if not username:
        raise RuntimeError("A username must be provided in environment variable UNAME")

    if not password:
        raise RuntimeError("A password must be specified in environment variable PASSWORD")

    if not root_path_env:
        root_path = pathlib.Path(__file__).parent.resolve() / "stories"
        logger.warning("No download path specified in the ROOTPATH environment variable, using %s", root_path)
    else:
        root_path = pathlib.Path(root_path_env)
        logger.info("Using download path %s", root_path)

    if not root_path.exists():
        logger.info("Download path %s does not exist, creating it", root_path)
        root_path.mkdir()

    
    storypark.login(username, password)

    # Assume if an error occurs you'll re-run it, make sure we attempt to logout in an error scenario
    try:
        download_all_stories(child_id, root_path)
    except:
        storypark.logout()
        raise    

    storypark.logout()



if __name__ == "__main__":
    main()
